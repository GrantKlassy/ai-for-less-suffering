"""Emit Palantir analyses as canonical JSON + prose companion markdown.

JSON is the source of truth for downstream renderers (Astro). Prose is shaped for
human reading; it does not introduce new facts --- only a flatter presentation of
what the JSON already contains.
"""

from __future__ import annotations

import json
from pathlib import Path

from afls.queries.leverage import (
    InterventionCoalitionAnalysis,
    LeverageAnalysis,
    LeverageRanking,
    RankingBlindSpot,
)
from afls.queries.palantir import (
    ContestedClaim,
    ConvergentInterventionAnalysis,
    EvidenceSummary,
    PalantirAnalysis,
)
from afls.queries.steelman import SteelmanAnalysis, SteelmanFrame
from afls.schema import (
    BlindSpot,
    Bridge,
    Camp,
    DescriptiveClaim,
    Intervention,
    NormativeClaim,
)
from afls.storage import list_nodes


def _stamp_slug(analysis: PalantirAnalysis) -> str:
    return analysis.generated_at.strftime("%Y%m%dT%H%M%SZ")


def analysis_paths(public_output_dir: Path, analysis: PalantirAnalysis) -> tuple[Path, Path]:
    """Return (json_path, md_path) for an analysis based on its timestamp."""
    base = public_output_dir / "analyses"
    slug = _stamp_slug(analysis)
    return (base / f"palantir_{slug}.json", base / f"palantir_{slug}.md")


def write_analysis_json(analysis: PalantirAnalysis, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = analysis.model_dump(mode="json")
    with path.open("w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def render_analysis_markdown(analysis: PalantirAnalysis, data_dir: Path) -> str:
    """Shape the analysis into prose. Deterministic; no LLM call."""
    camps_by_id = {c.id: c for c in list_nodes(Camp, data_dir)}
    descriptives = {c.id: c for c in list_nodes(DescriptiveClaim, data_dir)}
    normatives = {c.id: c for c in list_nodes(NormativeClaim, data_dir)}
    interventions = {i.id: i for i in list_nodes(Intervention, data_dir)}

    parts = [
        "# Palantir coalition analysis",
        "",
        f"Generated: `{analysis.generated_at.isoformat()}`",
        "",
        "Camps analyzed: " + ", ".join(
            f"**{camps_by_id[cid].name}** (`{cid}`)"
            if cid in camps_by_id
            else f"`{cid}`"
            for cid in analysis.camps
        ),
        "",
        _render_descriptive_convergences(analysis, descriptives),
        _render_contested_claims(analysis.contested_claims),
        _render_convergent_interventions(
            analysis.convergent_interventions, interventions, normatives, camps_by_id
        ),
        _render_bridges(analysis.bridges, camps_by_id),
        _render_blindspots(analysis.blindspots, camps_by_id),
    ]
    return "\n".join(parts).rstrip() + "\n"


def _render_evidence_list(label: str, evidence_list: list[EvidenceSummary]) -> list[str]:
    if not evidence_list:
        return []
    lines = [f"_{label}:_"]
    for e in evidence_list:
        locator = f" --- {e.locator}" if e.locator else ""
        lines.append(
            f"- `{e.evidence_id}` ({e.method_tag}, weight {e.weight}) --- "
            f"{e.source_title}{locator}"
        )
    lines.append("")
    return lines


def _render_contested_claims(contested: list[ContestedClaim]) -> str:
    if not contested:
        return (
            "## Contested claims\n\nNo claims carry both supporting and contradicting "
            "evidence. Absence here is not proof of consensus --- it may mean the graph "
            "has only collected one side.\n"
        )
    lines = ["## Contested claims", ""]
    for item in contested:
        lines.append(f"### `{item.claim_id}` --- {item.claim_text}")
        lines.append("")
        lines.extend(_render_evidence_list("Supporting", item.supports))
        lines.extend(_render_evidence_list("Contradicting", item.contradicts))
        if item.qualifies:
            lines.extend(_render_evidence_list("Qualifying", item.qualifies))
    return "\n".join(lines) + "\n"


def _render_descriptive_convergences(
    analysis: PalantirAnalysis, descriptives: dict[str, DescriptiveClaim]
) -> str:
    if not analysis.descriptive_convergences:
        return "## Descriptive convergence\n\nNo claims are held across every camp.\n"
    lines = ["## Descriptive convergence", "", "Held by every analyzed camp:"]
    for cid in analysis.descriptive_convergences:
        claim = descriptives.get(cid)
        if claim is None:
            lines.append(f"- `{cid}` (missing)")
        else:
            lines.append(f"- `{cid}` --- {claim.text}")
    return "\n".join(lines) + "\n"


def _render_convergent_interventions(
    items: list[ConvergentInterventionAnalysis],
    interventions: dict[str, Intervention],
    normatives: dict[str, NormativeClaim],
    camps_by_id: dict[str, Camp],
) -> str:
    if not items:
        return "## Convergent interventions\n\nNo interventions reach >= 2-camp support.\n"
    lines = ["## Convergent interventions", ""]
    for item in items:
        intv = interventions.get(item.intervention_id)
        heading = intv.text if intv else item.intervention_id
        lines.append(f"### {heading}")
        lines.append(f"_{item.intervention_id}_\n")
        if item.operator_note:
            lines.append(f"> {item.operator_note}\n")
        lines.append("Supporters and divergent anchors:")
        for camp_id in item.supporting_camps:
            camp_name = camps_by_id[camp_id].name if camp_id in camps_by_id else camp_id
            norm_id = item.divergent_reasons.get(camp_id)
            if norm_id is None:
                lines.append(f"- **{camp_name}** (`{camp_id}`) --- no explicit anchor given")
                continue
            norm = normatives.get(norm_id)
            norm_text = norm.text if norm else "(missing normative claim)"
            lines.append(f"- **{camp_name}** (`{camp_id}`) --- `{norm_id}`: {norm_text}")
        lines.append("")
    return "\n".join(lines)


def _render_bridges(bridges: list[Bridge], camps_by_id: dict[str, Camp]) -> str:
    if not bridges:
        return "## Bridges\n\nNo bridges generated.\n"
    lines = ["## Bridges", ""]
    for bridge in bridges:
        from_name = (
            camps_by_id[bridge.from_camp].name
            if bridge.from_camp in camps_by_id
            else bridge.from_camp
        )
        to_name = (
            camps_by_id[bridge.to_camp].name
            if bridge.to_camp in camps_by_id
            else bridge.to_camp
        )
        lines.append(f"### {from_name} -> {to_name}")
        lines.append(f"_{bridge.id}_\n")
        lines.append(bridge.translation)
        if bridge.caveats:
            lines.append("\n**Does not translate:**")
            for caveat in bridge.caveats:
                lines.append(f"- {caveat}")
        lines.append("")
    return "\n".join(lines)


def _render_blindspots(blindspots: list[BlindSpot], camps_by_id: dict[str, Camp]) -> str:
    if not blindspots:
        return "## Blindspots\n\nNone flagged.\n"
    lines = ["## Blindspots", "", "Flagged against operator priors (GRANT_BRAIN.md):", ""]
    for blindspot in blindspots:
        camp_name = (
            camps_by_id[blindspot.flagged_camp_id].name
            if blindspot.flagged_camp_id in camps_by_id
            else blindspot.flagged_camp_id
        )
        lines.append(
            f"- **{camp_name}** (`{blindspot.flagged_camp_id}`): {blindspot.reasoning}"
        )
    return "\n".join(lines) + "\n"


def write_analysis_markdown(analysis: PalantirAnalysis, path: Path, data_dir: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_analysis_markdown(analysis, data_dir))


def _leverage_stamp_slug(analysis: LeverageAnalysis) -> str:
    return analysis.generated_at.strftime("%Y%m%dT%H%M%SZ")


def leverage_analysis_paths(
    public_output_dir: Path, analysis: LeverageAnalysis
) -> tuple[Path, Path]:
    base = public_output_dir / "analyses"
    slug = _leverage_stamp_slug(analysis)
    return (base / f"leverage_{slug}.json", base / f"leverage_{slug}.md")


def write_leverage_json(analysis: LeverageAnalysis, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = analysis.model_dump(mode="json")
    with path.open("w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def render_leverage_markdown(analysis: LeverageAnalysis, data_dir: Path) -> str:
    camps_by_id = {c.id: c for c in list_nodes(Camp, data_dir)}
    descriptives = {c.id: c for c in list_nodes(DescriptiveClaim, data_dir)}
    interventions = {i.id: i for i in list_nodes(Intervention, data_dir)}

    parts = [
        "# Leverage analysis",
        "",
        f"Generated: `{analysis.generated_at.isoformat()}`",
        "",
        "Camps analyzed: "
        + ", ".join(
            f"**{camps_by_id[cid].name}** (`{cid}`)"
            if cid in camps_by_id
            else f"`{cid}`"
            for cid in analysis.camps
        ),
        "",
        "Friction semantic: `1 = no friction`, `0 = fully blocked`. "
        "Suffering semantic: `1 = maximum reduction`, `0 = none`. "
        "Composite: `suffering_composite = leverage x mean(friction) x "
        "mean(suffering_reduction)` --- the directive's -SUFFERING EV. "
        "Rankings sort by `suffering_composite`; the `viability` column is the "
        "old `leverage x mean(friction)` score kept for comparison.",
        "",
        _render_leverage_rankings(analysis.rankings),
        _render_coalition_analyses(
            analysis.coalition_analyses, interventions, camps_by_id
        ),
        _render_ranking_blindspots(analysis.ranking_blindspots, interventions),
        _render_leverage_descriptive_convergences(analysis, descriptives),
        _render_contested_claims(analysis.contested_claims),
    ]
    return "\n".join(parts).rstrip() + "\n"


def _render_leverage_rankings(rankings: list[LeverageRanking]) -> str:
    if not rankings:
        return "## Rankings\n\nNo interventions to rank.\n"
    lines = ["## Rankings (deterministic, sorted by -SUFFERING EV)", ""]
    for i, row in enumerate(rankings, start=1):
        lines.append(
            f"{i}. **`{row.intervention_id}`** --- "
            f"suffering_composite `{row.suffering_composite:.3f}` "
            f"= viability `{row.composite_score:.3f}` x "
            f"suffering `{row.mean_suffering_reduction:.3f}` "
            f"(leverage `{row.leverage_score}`, robustness "
            f"`{row.mean_robustness:.3f}`)"
        )
        lines.append(f"   > {row.intervention_text}")
    return "\n".join(lines) + "\n"


def _render_coalition_analyses(
    items: list[InterventionCoalitionAnalysis],
    interventions: dict[str, Intervention],
    camps_by_id: dict[str, Camp],
) -> str:
    if not items:
        return "## Coalition analysis\n\nNo coalition analyses returned.\n"
    lines = ["## Coalition analysis", ""]

    def _camp_names(ids: list[str]) -> str:
        if not ids:
            return "_(none)_"
        return ", ".join(
            f"**{camps_by_id[cid].name}**" if cid in camps_by_id else f"`{cid}`"
            for cid in ids
        )

    for item in items:
        intv = interventions.get(item.intervention_id)
        heading = intv.text if intv else item.intervention_id
        lines.append(f"### {heading}")
        lines.append(f"_{item.intervention_id}_\n")
        lines.append(f"**Supporting:** {_camp_names(item.supporting_camps)}")
        lines.append(f"**Contesting:** {_camp_names(item.contesting_camps)}")
        lines.append("")
        lines.append(item.expected_friction)
        lines.append("")
    return "\n".join(lines)


def _render_ranking_blindspots(
    blindspots: list[RankingBlindSpot], interventions: dict[str, Intervention]
) -> str:
    if not blindspots:
        return "## Ranking blindspots\n\nNone flagged.\n"
    lines = [
        "## Ranking blindspots",
        "",
        "Flagged against the deterministic composite --- where the ranking is "
        "likely mispriced given the camp graph:",
        "",
    ]
    for b in blindspots:
        intv = interventions.get(b.flagged_intervention_id)
        text = intv.text if intv else b.flagged_intervention_id
        lines.append(
            f"- **`{b.flagged_intervention_id}`** ({text}): {b.reasoning}"
        )
    return "\n".join(lines) + "\n"


def _render_leverage_descriptive_convergences(
    analysis: LeverageAnalysis, descriptives: dict[str, DescriptiveClaim]
) -> str:
    if not analysis.descriptive_convergences:
        return "## Descriptive convergence\n\nNo claims are held across every camp.\n"
    lines = ["## Descriptive convergence", "", "Held by every analyzed camp:"]
    for cid in analysis.descriptive_convergences:
        claim = descriptives.get(cid)
        if claim is None:
            lines.append(f"- `{cid}` (missing)")
        else:
            lines.append(f"- `{cid}` --- {claim.text}")
    return "\n".join(lines) + "\n"


def write_leverage_markdown(
    analysis: LeverageAnalysis, path: Path, data_dir: Path
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_leverage_markdown(analysis, data_dir))


def _steelman_stamp_slug(analysis: SteelmanAnalysis) -> str:
    return analysis.generated_at.strftime("%Y%m%dT%H%M%SZ")


def steelman_analysis_paths(
    public_output_dir: Path, analysis: SteelmanAnalysis
) -> tuple[Path, Path]:
    base = public_output_dir / "analyses"
    slug = _steelman_stamp_slug(analysis)
    return (base / f"steelman_{slug}.json", base / f"steelman_{slug}.md")


def write_steelman_json(analysis: SteelmanAnalysis, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = analysis.model_dump(mode="json")
    with path.open("w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def _render_steelman_frame(
    frame: SteelmanFrame,
    normatives: dict[str, NormativeClaim],
    descriptives: dict[str, DescriptiveClaim],
) -> list[str]:
    lines = [f"#### `{frame.camp_id}`", "", frame.case, ""]
    if frame.normative_claim_ids:
        lines.append("_Normative anchors:_")
        for nid in frame.normative_claim_ids:
            norm = normatives.get(nid)
            if norm is None:
                lines.append(f"- `{nid}` (missing)")
            else:
                lines.append(f"- `{nid}` --- {norm.text}")
        lines.append("")
    if frame.descriptive_claim_ids:
        lines.append("_Descriptive evidence:_")
        for did in frame.descriptive_claim_ids:
            claim = descriptives.get(did)
            if claim is None:
                lines.append(f"- `{did}` (missing)")
            else:
                lines.append(f"- `{did}` --- {claim.text}")
        lines.append("")
    return lines


def render_steelman_markdown(analysis: SteelmanAnalysis, data_dir: Path) -> str:
    descriptives = {c.id: c for c in list_nodes(DescriptiveClaim, data_dir)}
    normatives = {c.id: c for c in list_nodes(NormativeClaim, data_dir)}

    parts = [
        "# Steelman analysis",
        "",
        f"Generated: `{analysis.generated_at.isoformat()}`",
        "",
        f"Target intervention: **`{analysis.target_intervention_id}`** --- "
        f"{analysis.target_intervention_text}",
        "",
    ]

    parts.append("## Operator tension")
    parts.append("")
    parts.append("> " + analysis.operator_tension.replace("\n", "\n> "))
    parts.append("")

    parts.append("## Conceded descriptive ground")
    parts.append("")
    if not analysis.conceded_descriptive:
        parts.append(
            "No descriptive claims are cited by both FOR and AGAINST. Absence here "
            "means the sides are not yet arguing over shared evidence --- the data "
            "fill is thin or the frames are disjoint.\n"
        )
    else:
        parts.append("Claims cited by at least one FOR frame AND one AGAINST frame:")
        for cid in analysis.conceded_descriptive:
            claim = descriptives.get(cid)
            if claim is None:
                parts.append(f"- `{cid}` (missing)")
            else:
                parts.append(f"- `{cid}` --- {claim.text}")
        parts.append("")

    parts.append("## Case FOR")
    parts.append("")
    if not analysis.case_for:
        parts.append("_No FOR frames generated._\n")
    else:
        for frame in analysis.case_for:
            parts.extend(_render_steelman_frame(frame, normatives, descriptives))

    parts.append("## Case AGAINST")
    parts.append("")
    if not analysis.case_against:
        parts.append("_No AGAINST frames generated._\n")
    else:
        for frame in analysis.case_against:
            parts.extend(_render_steelman_frame(frame, normatives, descriptives))

    parts.append(_render_contested_claims(analysis.contested_claims))

    return "\n".join(parts).rstrip() + "\n"


def write_steelman_markdown(
    analysis: SteelmanAnalysis, path: Path, data_dir: Path
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_steelman_markdown(analysis, data_dir))
