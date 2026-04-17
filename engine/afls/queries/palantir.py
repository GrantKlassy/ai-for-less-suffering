"""Palantir coalition query.

Descriptive convergence is computed deterministically. Bridges, blindspots, and
per-intervention divergent-reason analysis come from a single LLM call (Opus by
default) with the operator context (BRAIN/MANIFESTO/CLAUDE) cached upstream.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from afls.reasoning import AnthropicClient, Model, complete_and_parse
from afls.schema import (
    BlindSpot,
    Bridge,
    Camp,
    DescriptiveClaim,
    Intervention,
    NormativeClaim,
    new_id,
)
from afls.storage import list_nodes

DEFAULT_CAMP_IDS: tuple[str, ...] = ("camp_palantir", "camp_anthropic", "camp_operator")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ConvergentInterventionAnalysis(_StrictModel):
    """Which camps support an intervention, and the normative anchor each gives for it."""

    intervention_id: str
    supporting_camps: list[str] = Field(min_length=2)
    divergent_reasons: dict[str, str] = Field(
        description="camp_id -> normative_claim_id: why this camp supports this intervention."
    )
    operator_note: str = Field(
        default="",
        description="One-line operator-framed commentary. No hedging, no manifesto voice.",
    )


class BridgeProposal(_StrictModel):
    """LLM-generated bridge. Converted to Bridge node in the final analysis."""

    from_camp: str
    to_camp: str
    translation: str = Field(min_length=1)
    caveats: list[str] = Field(default_factory=list)


class BlindSpotProposal(_StrictModel):
    """LLM-generated blindspot flagged against operator priors."""

    flagged_camp_id: str
    reasoning: str = Field(min_length=1)


class PalantirLLMOutput(_StrictModel):
    """Complete schema the LLM must return for the Palantir query."""

    convergent_interventions: list[ConvergentInterventionAnalysis] = Field(default_factory=list)
    bridges: list[BridgeProposal] = Field(default_factory=list)
    blindspots: list[BlindSpotProposal] = Field(default_factory=list)


class PalantirAnalysis(BaseModel):
    """Canonical output written to `public-output/analyses/palantir_<timestamp>.json`."""

    model_config = ConfigDict(extra="forbid")

    kind: ClassVar[str] = "palantir_analysis"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    camps: list[str]
    descriptive_convergences: list[str]
    convergent_interventions: list[ConvergentInterventionAnalysis]
    bridges: list[Bridge]
    blindspots: list[BlindSpot]


def find_descriptive_convergences(camps: list[Camp]) -> list[str]:
    """Descriptive claim IDs held by *every* provided camp. Sorted for determinism."""
    if not camps:
        return []
    shared = set(camps[0].held_descriptive)
    for camp in camps[1:]:
        shared &= set(camp.held_descriptive)
    return sorted(shared)


def _format_camp(camp: Camp, claims_by_id: dict[str, DescriptiveClaim | NormativeClaim]) -> str:
    lines = [f"- id: {camp.id}", f"  name: {camp.name}", f"  summary: {camp.summary}"]
    lines.append("  held_descriptive:")
    for ref in camp.held_descriptive:
        claim = claims_by_id.get(ref)
        text = claim.text if claim else "(missing)"
        lines.append(f"    - {ref}: {text}")
    lines.append("  held_normative:")
    for ref in camp.held_normative:
        claim = claims_by_id.get(ref)
        if isinstance(claim, NormativeClaim):
            lines.append(f"    - {ref}: [{claim.axiom_family.value}] {claim.text}")
        else:
            lines.append(f"    - {ref}: (missing)")
    return "\n".join(lines)


def _format_intervention(intv: Intervention) -> str:
    lines = [
        f"- id: {intv.id}",
        f"  text: {intv.text}",
        f"  action_kind: {intv.action_kind.value}",
        f"  leverage_score: {intv.leverage_score}",
    ]
    if intv.friction_scores:
        lines.append("  friction_scores:")
        for layer_id, score in sorted(intv.friction_scores.items()):
            lines.append(f"    {layer_id}: {score}")
    return "\n".join(lines)


def build_graph_context(
    camps: list[Camp],
    descriptives: list[DescriptiveClaim],
    normatives: list[NormativeClaim],
    interventions: list[Intervention],
) -> str:
    """Render the slice of graph state the LLM needs to reason over."""
    claims_by_id: dict[str, DescriptiveClaim | NormativeClaim] = {}
    for desc in descriptives:
        claims_by_id[desc.id] = desc
    for norm in normatives:
        claims_by_id[norm.id] = norm

    sections = ["# Current graph (camps, claims, interventions)", "", "## Camps"]
    for camp in camps:
        sections.append(_format_camp(camp, claims_by_id))
    sections.append("\n## Interventions")
    for intv in interventions:
        sections.append(_format_intervention(intv))
    return "\n".join(sections)


_USER_PROMPT = """Analyze the Palantir coalition question for this graph.

For each intervention, identify the camps that would support it and map each supporting \
camp to the normative_claim_id that explains *why* they support it (divergent reasons). \
Only include interventions with >= 2 supporting camps.

For each camp pair, generate a bridge --- a normative translation that lets one camp \
understand the other's position in its own framing, *without* collapsing the normative \
difference. Caveats mark what does not translate.

Against the operator's priors (BRAIN.md), flag blindspots: camps or positions the operator \
is likely under-weighting, with one-sentence reasoning each.

Return ONLY JSON matching the schema in the system prompt."""


def run_palantir_query(
    client: AnthropicClient,
    data_dir: Path,
    *,
    camp_ids: tuple[str, ...] = DEFAULT_CAMP_IDS,
    model: Model = Model.OPUS,
) -> PalantirAnalysis:
    """Load graph, compute deterministic convergence, ask LLM, assemble the analysis."""
    wanted = set(camp_ids)
    camps = [c for c in list_nodes(Camp, data_dir) if c.id in wanted]
    camps.sort(key=lambda c: camp_ids.index(c.id))
    if len(camps) != len(camp_ids):
        found = {c.id for c in camps}
        missing = sorted(wanted - found)
        raise RuntimeError(f"missing expected camps: {missing}")

    descriptives = list_nodes(DescriptiveClaim, data_dir)
    normatives = list_nodes(NormativeClaim, data_dir)
    interventions = list_nodes(Intervention, data_dir)

    desc_convs = find_descriptive_convergences(camps)
    context = build_graph_context(camps, descriptives, normatives, interventions)

    llm_out = complete_and_parse(
        client,
        model_cls=PalantirLLMOutput,
        user_message=_USER_PROMPT,
        extra_context=context,
        model=model,
    )

    bridges = [
        Bridge(
            id=new_id("bridge"),
            from_camp=proposal.from_camp,
            to_camp=proposal.to_camp,
            translation=proposal.translation,
            caveats=proposal.caveats,
        )
        for proposal in llm_out.bridges
    ]
    blindspots = [
        BlindSpot(
            id=new_id("blind"),
            against_prior_set="BRAIN.md",
            flagged_camp_id=proposal.flagged_camp_id,
            reasoning=proposal.reasoning,
        )
        for proposal in llm_out.blindspots
    ]

    return PalantirAnalysis(
        camps=[c.id for c in camps],
        descriptive_convergences=desc_convs,
        convergent_interventions=llm_out.convergent_interventions,
        bridges=bridges,
        blindspots=blindspots,
    )
