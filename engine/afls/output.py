"""Emit coalition analyses as canonical JSON + prose companion markdown.

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
from afls.queries.coalition import (
    CoalitionAnalysis,
    ContestedClaim,
    ConvergentInterventionAnalysis,
    EvidenceSummary,
)
from afls.queries.reallocation import (
    HARM_DIVERGENCE_THRESHOLD,
    ReallocationAnalysis,
    ReallocationBlindSpot,
    ReallocationCoalitionShift,
    ReallocationPair,
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


def _stamp_slug(analysis: CoalitionAnalysis) -> str:
    return analysis.generated_at.strftime("%Y%m%dT%H%M%SZ")


def analysis_paths(public_output_dir: Path, analysis: CoalitionAnalysis) -> tuple[Path, Path]:
    """Return (json_path, md_path) for an analysis based on its timestamp."""
    base = public_output_dir / "analyses"
    slug = _stamp_slug(analysis)
    return (base / f"coalition_{slug}.json", base / f"coalition_{slug}.md")


def write_analysis_json(analysis: CoalitionAnalysis, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = analysis.model_dump(mode="json")
    with path.open("w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def render_analysis_markdown(analysis: CoalitionAnalysis, data_dir: Path) -> str:
    """Shape the analysis into prose. Deterministic; no LLM call."""
    camps_by_id = {c.id: c for c in list_nodes(Camp, data_dir)}
    descriptives = {c.id: c for c in list_nodes(DescriptiveClaim, data_dir)}
    normatives = {c.id: c for c in list_nodes(NormativeClaim, data_dir)}
    interventions = {i.id: i for i in list_nodes(Intervention, data_dir)}

    parts = [
        "# Coalition analysis",
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
    analysis: CoalitionAnalysis, descriptives: dict[str, DescriptiveClaim]
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


def write_analysis_markdown(analysis: CoalitionAnalysis, path: Path, data_dir: Path) -> None:
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
        "Harm semantic: `1 = no harm`, `0 = maximum harm` (same polarity as "
        "friction). Suffering semantic: `1 = maximum reduction`, `0 = none`. "
        "Composites (nested): `viability = leverage x mean(friction)`; "
        "`suffering_composite = viability x mean(suffering_reduction)`; "
        "`net_composite = suffering_composite x mean(harm_robustness)`. "
        "Rankings sort by `net_composite` --- the directive's -SUFFERING EV "
        "net of harm caused if the intervention lands. `viability` and "
        "`suffering_composite` are kept alongside so the marginal effect of "
        "each term is legible.",
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
    lines = [
        "## Rankings (deterministic, sorted by -SUFFERING EV net of harm)",
        "",
    ]
    for i, row in enumerate(rankings, start=1):
        lines.append(
            f"{i}. **`{row.intervention_id}`** --- "
            f"net_composite `{row.net_composite:.3f}` "
            f"= suffering_composite `{row.suffering_composite:.3f}` x "
            f"harm_robustness `{row.mean_harm_robustness:.3f}` "
            f"(viability `{row.composite_score:.3f}`, suffering "
            f"`{row.mean_suffering_reduction:.3f}`, leverage "
            f"`{row.leverage_score}`, robustness `{row.mean_robustness:.3f}`)"
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


def _reallocation_stamp_slug(analysis: ReallocationAnalysis) -> str:
    return analysis.generated_at.strftime("%Y%m%dT%H%M%SZ")


def reallocation_analysis_paths(
    public_output_dir: Path, analysis: ReallocationAnalysis
) -> tuple[Path, Path]:
    base = public_output_dir / "analyses"
    slug = _reallocation_stamp_slug(analysis)
    return (base / f"reallocation_{slug}.json", base / f"reallocation_{slug}.md")


def write_reallocation_json(analysis: ReallocationAnalysis, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = analysis.model_dump(mode="json")
    with path.open("w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def _render_reallocation_pair(
    pair: ReallocationPair, interventions: dict[str, Intervention]
) -> list[str]:
    from_text = (
        interventions[pair.from_intervention_id].text
        if pair.from_intervention_id in interventions
        else pair.from_intervention_id
    )
    to_text = (
        interventions[pair.to_intervention_id].text
        if pair.to_intervention_id in interventions
        else pair.to_intervention_id
    )
    harm_flag = (
        " **[harm flag]**"
        if pair.delta_harm_robustness < -HARM_DIVERGENCE_THRESHOLD
        else ""
    )
    return [
        f"- **`{pair.from_intervention_id}`** -> "
        f"**`{pair.to_intervention_id}`**{harm_flag}",
        f"  - delta_net `{pair.delta_net:+.3f}` "
        f"(from `{pair.from_net_composite:.3f}` -> to "
        f"`{pair.to_net_composite:.3f}`)",
        f"  - delta_suffering_composite `{pair.delta_suffering_composite:+.3f}` "
        f"· delta_harm_robustness `{pair.delta_harm_robustness:+.3f}` "
        f"· delta_viability `{pair.delta_viability:+.3f}`",
        f"  - from: {from_text}",
        f"  - to: {to_text}",
    ]


def _render_reallocation_pairs(
    pairs: list[ReallocationPair], interventions: dict[str, Intervention]
) -> str:
    if not pairs:
        return (
            "## Reallocation pairs\n\nNo pairs with positive delta_net. "
            "Either the interventions are symmetric or the graph is too "
            "sparse for a reallocation to register.\n"
        )
    lines = [
        "## Reallocation pairs (sorted by delta_net descending)",
        "",
        "Each pair is a proposed shift: move AI effort from the source "
        "(`from`) to the destination (`to`). Only pairs with positive "
        "`delta_net` are listed --- trivially-bad moves are omitted.",
        "",
    ]
    for pair in pairs:
        lines.extend(_render_reallocation_pair(pair, interventions))
    return "\n".join(lines) + "\n"


def _render_harm_divergence_flags(
    flagged: list[ReallocationPair], interventions: dict[str, Intervention]
) -> str:
    if not flagged:
        return (
            "## Harm divergence flags\n\nNo pairs with delta_harm_robustness "
            f"below -{HARM_DIVERGENCE_THRESHOLD}. Current graph does not "
            "contain a reallocation that trades suffering reduction for "
            "material harm.\n"
        )
    lines = [
        "## Harm divergence flags",
        "",
        "Pairs whose destination is materially dirtier than the source "
        f"(delta_harm_robustness < -{HARM_DIVERGENCE_THRESHOLD}). A pair in "
        "both this list and `Reallocation pairs` is a suffering-gain-at-"
        "harm-cost trade --- positive delta_net, negative harm delta, the "
        "exact trade the composite has priced but the operator should see "
        "explicitly.",
        "",
    ]
    for pair in flagged:
        lines.extend(_render_reallocation_pair(pair, interventions))
    return "\n".join(lines) + "\n"


def _render_coalition_shifts(
    shifts: list[ReallocationCoalitionShift],
    interventions: dict[str, Intervention],
    camps_by_id: dict[str, Camp],
) -> str:
    if not shifts:
        return "## Coalition shifts\n\nNo coalition shifts returned.\n"
    lines = ["## Coalition shifts", ""]

    def _camp_names(ids: list[str]) -> str:
        if not ids:
            return "_(none)_"
        return ", ".join(
            f"**{camps_by_id[cid].name}**" if cid in camps_by_id else f"`{cid}`"
            for cid in ids
        )

    for shift in shifts:
        from_text = (
            interventions[shift.from_intervention_id].text
            if shift.from_intervention_id in interventions
            else shift.from_intervention_id
        )
        to_text = (
            interventions[shift.to_intervention_id].text
            if shift.to_intervention_id in interventions
            else shift.to_intervention_id
        )
        lines.append(
            f"### `{shift.from_intervention_id}` -> `{shift.to_intervention_id}`"
        )
        lines.append(f"_{from_text} -> {to_text}_\n")
        lines.append(f"**Gaining:** {_camp_names(shift.gaining_camps)}")
        lines.append(f"**Losing:** {_camp_names(shift.losing_camps)}")
        lines.append("")
        lines.append(shift.friction_rebinds)
        lines.append("")
    return "\n".join(lines)


def _render_reallocation_blindspots(
    blindspots: list[ReallocationBlindSpot],
) -> str:
    if not blindspots:
        return "## Reallocation blindspots\n\nNone flagged.\n"
    lines = [
        "## Reallocation blindspots",
        "",
        "Flagged against the deterministic pair-delta --- moves the composite "
        "likely mis-prices given the camp graph:",
        "",
    ]
    for b in blindspots:
        lines.append(
            f"- **`{b.flagged_from_intervention_id}`** -> "
            f"**`{b.flagged_to_intervention_id}`**: {b.reasoning}"
        )
    return "\n".join(lines) + "\n"


def render_reallocation_markdown(
    analysis: ReallocationAnalysis, data_dir: Path
) -> str:
    camps_by_id = {c.id: c for c in list_nodes(Camp, data_dir)}
    interventions = {i.id: i for i in list_nodes(Intervention, data_dir)}
    descriptives = {c.id: c for c in list_nodes(DescriptiveClaim, data_dir)}

    parts = [
        "# Reallocation analysis",
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
        "`net_composite = leverage x mean(friction) x mean(suffering_reduction) "
        "x mean(harm_robustness)`. A reallocation pair (`from -> to`) shifts "
        "AI effort; `delta_net` is the change in -SUFFERING EV net of harm. "
        "Only positive-delta pairs are listed as candidates; "
        "harm-divergence flags are orthogonal.",
        "",
        _render_reallocation_pairs(analysis.pairs, interventions),
        _render_harm_divergence_flags(analysis.harm_divergence_flags, interventions),
        _render_coalition_shifts(
            analysis.coalition_shifts, interventions, camps_by_id
        ),
        _render_reallocation_blindspots(analysis.reallocation_blindspots),
        _render_leverage_descriptive_convergences_from_reallocation(
            analysis, descriptives
        ),
        _render_contested_claims(analysis.contested_claims),
    ]
    return "\n".join(parts).rstrip() + "\n"


def _render_leverage_descriptive_convergences_from_reallocation(
    analysis: ReallocationAnalysis, descriptives: dict[str, DescriptiveClaim]
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


def write_reallocation_markdown(
    analysis: ReallocationAnalysis, path: Path, data_dir: Path
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_reallocation_markdown(analysis, data_dir))
