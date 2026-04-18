"""Leverage query.

Ranks interventions by `leverage_score x mean(friction_scores) x mean(suffering_reduction_scores)`.
The ranking is deterministic and operator-authored --- the LLM does not invent
leverage, friction, or suffering-reduction numbers. One Opus pass layers coalition
analysis per ranked intervention: which camps line up, which contest it, what the
expected friction fight looks like, and whether the suffering numerator is plausible.

The composite formula is the -SUFFERING EV the directive asks for. Interventions
with zero suffering_reduction_scores rank zero regardless of political viability;
that is intentional. The old viability composite (`leverage x robustness`) is kept
alongside so the suffering term's effect on the ranking is legible.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from afls.queries.palantir import (
    ContestedClaim,
    find_contested_claims,
    find_descriptive_convergences,
)
from afls.reasoning import AnthropicClient, Model, complete_and_parse
from afls.schema import (
    Camp,
    DescriptiveClaim,
    Evidence,
    Intervention,
    NormativeClaim,
    Source,
)
from afls.storage import list_nodes

DEFAULT_CAMP_IDS: tuple[str, ...] = (
    "camp_palantir",
    "camp_anthropic",
    "camp_operator",
    "camp_displaced_workers",
    "camp_xrisk",
    "camp_global_health",
    "camp_animal_welfare",
    "camp_biomedical",
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LeverageRanking(_StrictModel):
    """Deterministic ranking row. Computed from node fields, no LLM.

    Two composites. `composite_score` is the old viability number
    (`leverage x robustness`). `suffering_composite` multiplies in the suffering
    numerator and is the directive's -SUFFERING EV. Rankings sort by the latter.
    """

    intervention_id: str
    intervention_text: str
    leverage_score: float
    mean_robustness: float = Field(
        description="Mean of friction_scores values. Friction semantic: 1 = no "
        "friction, 0 = fully blocked. Higher is better."
    )
    mean_suffering_reduction: float = Field(
        description="Mean of suffering_reduction_scores values. Suffering "
        "semantic: 1 = maximum reduction, 0 = no reduction. Zero when scores "
        "are absent --- no suffering-reduction numerator, no -SUFFERING EV."
    )
    composite_score: float = Field(
        description="Viability: leverage_score x mean_robustness. Ignores what "
        "the intervention is pointed at."
    )
    suffering_composite: float = Field(
        description="-SUFFERING EV: composite_score x mean_suffering_reduction. "
        "What the directive actually asks the tool to rank by."
    )
    friction_scores: dict[str, float]
    suffering_reduction_scores: dict[str, float] = Field(default_factory=dict)


class InterventionCoalitionAnalysis(_StrictModel):
    """Per-intervention LLM output: who supports, who contests, friction read."""

    intervention_id: str
    supporting_camps: list[str] = Field(default_factory=list)
    contesting_camps: list[str] = Field(default_factory=list)
    expected_friction: str = Field(
        min_length=1,
        description="One paragraph, operator-framed, on where the friction actually "
        "binds. No hedging, no manifesto voice.",
    )


class RankingBlindSpot(_StrictModel):
    """Flag that the ranking is suspected to mis-price a specific intervention.

    Distinct from `schema.BlindSpot` (which targets camps). Ranking blindspots are
    ephemeral to the leverage analysis --- they are not graph nodes and do not get
    cross-referenced by other queries.
    """

    flagged_intervention_id: str = Field(
        description="Intervention the ranking is suspected to mis-price."
    )
    reasoning: str = Field(min_length=1)


class LeverageLLMOutput(_StrictModel):
    """Complete schema the LLM must return for the leverage query."""

    coalition_analyses: list[InterventionCoalitionAnalysis] = Field(default_factory=list)
    ranking_blindspots: list[RankingBlindSpot] = Field(default_factory=list)


class LeverageAnalysis(BaseModel):
    """Canonical output written to `public-output/analyses/leverage_<timestamp>.json`."""

    model_config = ConfigDict(extra="forbid")

    kind: ClassVar[str] = "leverage_analysis"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    camps: list[str]
    descriptive_convergences: list[str]
    rankings: list[LeverageRanking]
    coalition_analyses: list[InterventionCoalitionAnalysis]
    ranking_blindspots: list[RankingBlindSpot] = Field(default_factory=list)
    contested_claims: list[ContestedClaim] = Field(default_factory=list)


def _mean_robustness(intervention: Intervention) -> float:
    scores = list(intervention.friction_scores.values())
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _mean_suffering_reduction(intervention: Intervention) -> float:
    scores = list(intervention.suffering_reduction_scores.values())
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def rank_interventions(interventions: list[Intervention]) -> list[LeverageRanking]:
    """Deterministic ranking: suffering_composite descending, id as tie-break."""
    rows: list[LeverageRanking] = []
    for intv in interventions:
        robustness = _mean_robustness(intv)
        suffering = _mean_suffering_reduction(intv)
        composite = intv.leverage_score * robustness
        rows.append(
            LeverageRanking(
                intervention_id=intv.id,
                intervention_text=intv.text,
                leverage_score=intv.leverage_score,
                mean_robustness=robustness,
                mean_suffering_reduction=suffering,
                composite_score=composite,
                suffering_composite=composite * suffering,
                friction_scores=dict(intv.friction_scores),
                suffering_reduction_scores=dict(intv.suffering_reduction_scores),
            )
        )
    rows.sort(key=lambda r: (-r.suffering_composite, r.intervention_id))
    return rows


def _format_camp_terse(camp: Camp) -> str:
    held = ", ".join(camp.held_descriptive[:6])
    norms = ", ".join(camp.held_normative)
    return (
        f"- id: {camp.id} | name: {camp.name}\n"
        f"  summary: {camp.summary}\n"
        f"  held_descriptive (first 6): {held}\n"
        f"  held_normative: {norms}"
    )


def _format_ranking_row(row: LeverageRanking) -> str:
    friction = ", ".join(f"{k}={v}" for k, v in sorted(row.friction_scores.items()))
    suffering = ", ".join(
        f"{k}={v}" for k, v in sorted(row.suffering_reduction_scores.items())
    )
    return (
        f"- {row.intervention_id}: suffering_composite={row.suffering_composite:.3f} "
        f"(viability={row.composite_score:.3f} x "
        f"suffering={row.mean_suffering_reduction:.3f})\n"
        f"    viability = leverage={row.leverage_score} x "
        f"robustness={row.mean_robustness:.3f}\n"
        f"    text: {row.intervention_text}\n"
        f"    friction_scores: {friction}\n"
        f"    suffering_reduction_scores: {suffering or '(none)'}"
    )


def build_leverage_context(
    camps: list[Camp],
    rankings: list[LeverageRanking],
    descriptives: list[DescriptiveClaim],
    normatives: list[NormativeClaim],
) -> str:
    """Render the graph slice the LLM needs for coalition + blindspot reasoning."""
    claims_by_id: dict[str, DescriptiveClaim | NormativeClaim] = {}
    for d in descriptives:
        claims_by_id[d.id] = d
    for n in normatives:
        claims_by_id[n.id] = n

    sections = [
        "# Leverage ranking (deterministic) + camp registry",
        "",
        "Friction semantic: 1 = no friction, 0 = fully blocked. Higher = more robust.",
        "Suffering-reduction semantic: 1 = maximum reduction, 0 = no reduction. "
        "Absence of scores => zero suffering composite by design.",
        "",
        "Composite: suffering_composite = leverage x mean(friction) x "
        "mean(suffering_reduction). Rankings sort by suffering_composite.",
        "",
        "## Rankings (top to bottom)",
    ]
    for row in rankings:
        sections.append(_format_ranking_row(row))
    sections.append("\n## Camps")
    for camp in camps:
        sections.append(_format_camp_terse(camp))
    sections.append("\n## Normative claims referenced by camps")
    used_norms: set[str] = set()
    for camp in camps:
        used_norms.update(camp.held_normative)
    for nid in sorted(used_norms):
        claim = claims_by_id.get(nid)
        if isinstance(claim, NormativeClaim):
            sections.append(f"- {nid}: {claim.text}")
    return "\n".join(sections)


_USER_PROMPT = """Analyze this leverage ranking and the camps.

The ranking is deterministic --- suffering_composite = \
leverage x mean(friction) x mean(suffering_reduction). Do not second-guess the \
numbers; reason about the coalitions around them and the plausibility of the \
suffering numerator.

For each intervention in the ranking, return a `coalition_analyses` entry:
- `supporting_camps`: camps whose normative stack + held descriptives line up behind it
- `contesting_camps`: camps whose stance actively opposes or constrains it (not merely \
indifferent)
- `expected_friction`: one paragraph on (a) where the friction actually binds in \
practice and (b) whether the suffering_reduction_scores look right given the \
intervention's mechanism. Operator voice: specific, no hedging, no manifesto voice, \
name the binding constraint and name the suffering layer the intervention actually \
touches.

Then flag `ranking_blindspots` --- interventions whose suffering_composite is likely \
mispriced given the camp graph or the suffering layers. Examples of valid flags: the \
operator's leverage is higher than the camp coalition can plausibly move; a \
low-ranked intervention has cross-camp coalition support that the composite misses; \
mean_robustness masks a single-layer veto; a suffering_reduction_scores entry credits \
an intervention for a layer it doesn't actually touch; an intervention with zero \
suffering numerator is ranked at the bottom when its *enabling* role for \
suffering-reducing deployment is load-bearing. One sentence per flag, with the \
specific mechanism.

Return ONLY JSON matching the schema in the system prompt."""


def run_leverage_query(
    client: AnthropicClient,
    data_dir: Path,
    *,
    camp_ids: tuple[str, ...] = DEFAULT_CAMP_IDS,
    model: Model = Model.OPUS,
) -> LeverageAnalysis:
    """Load graph, rank deterministically, ask LLM, assemble the analysis."""
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
    evidence_list = list_nodes(Evidence, data_dir)
    sources = list_nodes(Source, data_dir)

    rankings = rank_interventions(interventions)
    desc_convs = find_descriptive_convergences(camps)
    contested = find_contested_claims(descriptives, evidence_list, sources)
    context = build_leverage_context(camps, rankings, descriptives, normatives)

    llm_out = complete_and_parse(
        client,
        model_cls=LeverageLLMOutput,
        user_message=_USER_PROMPT,
        extra_context=context,
        model=model,
    )

    return LeverageAnalysis(
        camps=[c.id for c in camps],
        descriptive_convergences=desc_convs,
        rankings=rankings,
        coalition_analyses=llm_out.coalition_analyses,
        ranking_blindspots=llm_out.ranking_blindspots,
        contested_claims=contested,
    )
