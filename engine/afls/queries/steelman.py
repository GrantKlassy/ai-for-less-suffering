"""Steelman query.

Given a contested intervention, produce the strongest case FOR and AGAINST it from
inside each camp in the graph. The point is not debate prep --- it is to force the
operator to read their own position from outside, and to surface what they would have
to concede to a frame they would otherwise filter out.

Deterministic pieces:
- `contested_descriptive` --- reuses `palantir.find_contested_claims`.
- `conceded_descriptive` --- descriptive claim IDs cited by both FOR and AGAINST.

LLM pieces (one Opus call):
- `case_for` / `case_against` per camp.
- `operator_tension` --- where the FOR/AGAINST split cuts across operator priors.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from afls.queries.palantir import (
    ContestedClaim,
    build_graph_context,
    find_contested_claims,
)
from afls.reasoning import AnthropicClient, Model, complete_and_parse
from afls.schema import (
    Camp,
    DescriptiveClaim,
    Evidence,
    FrictionLayer,
    HarmLayer,
    Intervention,
    NormativeClaim,
    Source,
)
from afls.storage import list_nodes


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SteelmanFrame(_StrictModel):
    """A case constructed from inside one camp.

    `camp_id` anchors the frame in a concrete coalition of agents; the LLM reasons
    from inside that camp's held claims. `normative_claim_ids` are anchors in the
    graph, `descriptive_claim_ids` are evidence the frame draws on. `case` is one
    operator-voiced paragraph --- no hedging, no manifesto voice, no filler.
    """

    camp_id: str = Field(min_length=1)
    normative_claim_ids: list[str] = Field(default_factory=list)
    descriptive_claim_ids: list[str] = Field(default_factory=list)
    case: str = Field(min_length=1)


class SteelmanLLMOutput(_StrictModel):
    """Complete schema the LLM must return for the steelman query."""

    case_for: list[SteelmanFrame] = Field(default_factory=list)
    case_against: list[SteelmanFrame] = Field(default_factory=list)
    operator_tension: str = Field(min_length=1)


class SteelmanAnalysis(BaseModel):
    """Canonical output written to `public-output/analyses/steelman_<timestamp>.json`."""

    model_config = ConfigDict(extra="forbid")

    kind: ClassVar[str] = "steelman_analysis"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    target_intervention_id: str
    target_intervention_text: str
    case_for: list[SteelmanFrame]
    case_against: list[SteelmanFrame]
    conceded_descriptive: list[str] = Field(default_factory=list)
    contested_claims: list[ContestedClaim] = Field(default_factory=list)
    operator_tension: str


def compute_conceded_descriptive(
    case_for: list[SteelmanFrame], case_against: list[SteelmanFrame]
) -> list[str]:
    """Descriptive claim IDs cited by at least one FOR frame AND one AGAINST frame.

    These are the facts of the matter both sides accept --- the conceded ground.
    """
    for_ids: set[str] = set()
    for frame in case_for:
        for_ids.update(frame.descriptive_claim_ids)
    against_ids: set[str] = set()
    for frame in case_against:
        against_ids.update(frame.descriptive_claim_ids)
    return sorted(for_ids & against_ids)


def _format_target_intervention(
    intv: Intervention,
    friction_layers: list[FrictionLayer],
    harm_layers: list[HarmLayer],
) -> str:
    """Render the target intervention with friction + harm scores, spotlighted."""
    friction_by_id = {fl.id: fl for fl in friction_layers}
    harm_by_id = {hl.id: hl for hl in harm_layers}
    lines = [
        f"- id: {intv.id}",
        f"  text: {intv.text}",
        f"  action_kind: {intv.action_kind.value}",
        f"  leverage_score: {intv.leverage_score}",
    ]
    if intv.cost_estimate:
        lines.append(f"  cost_estimate: {intv.cost_estimate}")
    if intv.friction_scores:
        lines.append("  friction_scores (1=no friction, 0=fully blocked):")
        for layer_id, score in sorted(intv.friction_scores.items()):
            name = friction_by_id[layer_id].name if layer_id in friction_by_id else layer_id
            lines.append(f"    {layer_id} ({name}): {score}")
    if intv.harm_scores:
        lines.append("  harm_scores (1=no harm, 0=maximum harm):")
        for layer_id, score in sorted(intv.harm_scores.items()):
            name = harm_by_id[layer_id].name if layer_id in harm_by_id else layer_id
            lines.append(f"    {layer_id} ({name}): {score}")
    return "\n".join(lines)


def _format_layer_glossary(
    friction_layers: list[FrictionLayer], harm_layers: list[HarmLayer]
) -> str:
    """Glossary block so the LLM knows what each score maps to."""
    lines = ["## Friction layers (what the intervention must survive)"]
    for fl in sorted(friction_layers, key=lambda x: x.id):
        lines.append(f"- `{fl.id}` ({fl.name}): {fl.description}")
    lines.append("")
    lines.append("## Harm layers (what the intervention costs if it succeeds)")
    for hl in sorted(harm_layers, key=lambda x: x.id):
        lines.append(f"- `{hl.id}` ({hl.name}): {hl.description}")
    return "\n".join(lines)


def build_steelman_context(
    target: Intervention,
    camps: list[Camp],
    descriptives: list[DescriptiveClaim],
    normatives: list[NormativeClaim],
    interventions: list[Intervention],
    friction_layers: list[FrictionLayer],
    harm_layers: list[HarmLayer],
    evidence_list: list[Evidence],
    sources: list[Source],
) -> str:
    """Render the graph slice the LLM needs to steelman the target intervention.

    Spotlights the target, glosses the friction/harm layers, then folds in the rest
    of the graph via `build_graph_context` so normative claims, descriptive claims,
    and evidence are all addressable by ID. Lists the camp IDs the LLM may frame
    from --- one case_for and one case_against per camp, at most.
    """
    present_camps = sorted(c.id for c in camps)
    sections = [
        "# Target intervention (spotlight)",
        "",
        _format_target_intervention(target, friction_layers, harm_layers),
        "",
        _format_layer_glossary(friction_layers, harm_layers),
        "",
        f"## Camps present: {', '.join(present_camps)}",
        "",
        build_graph_context(
            camps, descriptives, normatives, interventions, evidence_list, sources
        ),
    ]
    return "\n".join(sections)


_USER_PROMPT = """Construct the strongest case FOR and AGAINST the target intervention, \
from inside each camp present in the graph.

For each camp, produce up to two SteelmanFrame entries:
- one in `case_for`: the strongest case FOR the target from inside that camp's frame
- one in `case_against`: the strongest case AGAINST from inside the same camp

Each SteelmanFrame must:
- set `camp_id` to the camp it is reasoning inside (must exist in the graph)
- cite `normative_claim_ids` that exist in the graph (do NOT invent IDs); prefer the \
camp's own held_normative where it fits
- cite `descriptive_claim_ids` that exist in the graph as evidence (do NOT invent IDs)
- give a `case` that is one paragraph, operator-voiced, non-hedging. No manifesto voice. \
Do NOT dilute the case by hedging --- if you cannot find a real case from inside a camp, \
omit that frame entirely rather than produce a weak version.

Then write `operator_tension`: one paragraph on where the FOR/AGAINST split cuts across \
the operator's own priors in BRAIN.md. This is the sharp version of a blindspot --- name \
the specific case the operator should be uncomfortable with FROM INSIDE their own frame. \
Be specific, not abstract. Not a summary of the analysis.

Return ONLY JSON matching the schema in the system prompt."""


def run_steelman_query(
    client: AnthropicClient,
    data_dir: Path,
    *,
    target_intervention_id: str,
    model: Model = Model.OPUS,
) -> SteelmanAnalysis:
    """Load graph, spotlight target intervention, ask LLM, assemble the analysis."""
    interventions = list_nodes(Intervention, data_dir)
    target = next((i for i in interventions if i.id == target_intervention_id), None)
    if target is None:
        raise RuntimeError(f"unknown intervention: {target_intervention_id!r}")

    camps = list_nodes(Camp, data_dir)
    descriptives = list_nodes(DescriptiveClaim, data_dir)
    normatives = list_nodes(NormativeClaim, data_dir)
    friction_layers = list_nodes(FrictionLayer, data_dir)
    harm_layers = list_nodes(HarmLayer, data_dir)
    evidence_list = list_nodes(Evidence, data_dir)
    sources = list_nodes(Source, data_dir)

    contested = find_contested_claims(descriptives, evidence_list, sources)
    context = build_steelman_context(
        target,
        camps,
        descriptives,
        normatives,
        interventions,
        friction_layers,
        harm_layers,
        evidence_list,
        sources,
    )

    llm_out = complete_and_parse(
        client,
        model_cls=SteelmanLLMOutput,
        user_message=_USER_PROMPT,
        extra_context=context,
        model=model,
    )

    conceded = compute_conceded_descriptive(llm_out.case_for, llm_out.case_against)

    return SteelmanAnalysis(
        target_intervention_id=target.id,
        target_intervention_text=target.text,
        case_for=llm_out.case_for,
        case_against=llm_out.case_against,
        conceded_descriptive=conceded,
        contested_claims=contested,
        operator_tension=llm_out.operator_tension,
    )
