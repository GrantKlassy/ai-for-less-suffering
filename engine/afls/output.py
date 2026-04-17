"""Emit Palantir analyses as canonical JSON + prose companion markdown.

JSON is the source of truth for downstream renderers (Astro). Prose is shaped for
human reading; it does not introduce new facts --- only a flatter presentation of
what the JSON already contains.
"""

from __future__ import annotations

import json
from pathlib import Path

from afls.queries.palantir import (
    ConvergentInterventionAnalysis,
    PalantirAnalysis,
)
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
        _render_convergent_interventions(
            analysis.convergent_interventions, interventions, normatives, camps_by_id
        ),
        _render_bridges(analysis.bridges, camps_by_id),
        _render_blindspots(analysis.blindspots, camps_by_id),
    ]
    return "\n".join(parts).rstrip() + "\n"


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
    lines = ["## Blindspots", "", "Flagged against operator priors (BRAIN.md):", ""]
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
