"""Leverage query.

Ranks interventions by `leverage_score x mean(friction_scores)`. The ranking is
deterministic and operator-authored --- the LLM does not invent leverage numbers.
One Opus pass layers coalition analysis per ranked intervention: which camps line
up, which contest it, what the expected friction fight looks like.
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
    Intervention,
    NormativeClaim,
    Source,
    Warrant,
)
from afls.storage import list_nodes

DEFAULT_CAMP_IDS: tuple[str, ...] = (
    "camp_palantir",
    "camp_anthropic",
    "camp_operator",
    "camp_displaced_workers",
    "camp_xrisk",
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LeverageRanking(_StrictModel):
    """Deterministic ranking row. Computed from node fields, no LLM."""

    intervention_id: str
    intervention_text: str
    leverage_score: float
    mean_robustness: float = Field(
        description="Mean of friction_scores values. Friction semantic: 1 = no "
        "friction, 0 = fully blocked. Higher is better."
    )
    composite_score: float = Field(description="leverage_score x mean_robustness.")
    friction_scores: dict[str, float]


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


def rank_interventions(interventions: list[Intervention]) -> list[LeverageRanking]:
    """Deterministic ranking: leverage x robustness, descending."""
    rows: list[LeverageRanking] = []
    for intv in interventions:
        robustness = _mean_robustness(intv)
        rows.append(
            LeverageRanking(
                intervention_id=intv.id,
                intervention_text=intv.text,
                leverage_score=intv.leverage_score,
                mean_robustness=robustness,
                composite_score=intv.leverage_score * robustness,
                friction_scores=dict(intv.friction_scores),
            )
        )
    rows.sort(key=lambda r: (-r.composite_score, r.intervention_id))
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
    return (
        f"- {row.intervention_id}: composite={row.composite_score:.3f} "
        f"(leverage={row.leverage_score} x robustness={row.mean_robustness:.3f})\n"
        f"    text: {row.intervention_text}\n"
        f"    friction_scores: {friction}"
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
            sections.append(f"- {nid} [{claim.axiom_family.value}]: {claim.text}")
    return "\n".join(sections)


_USER_PROMPT = """Analyze this leverage ranking and the camps.

The ranking is deterministic --- leverage_score x mean_robustness. Do not second-guess
the numbers; reason about the coalitions around them.

For each intervention in the ranking, return a `coalition_analyses` entry:
- `supporting_camps`: camps whose normative stack + held descriptives line up behind it
- `contesting_camps`: camps whose stance actively opposes or constrains it (not merely \
indifferent)
- `expected_friction`: one paragraph on where the friction actually binds in practice. \
Operator voice: specific, no hedging, no manifesto voice, name the binding constraint.

Then flag `ranking_blindspots` --- interventions whose composite score is likely \
mispriced given the camp graph. Examples of valid flags: the operator's leverage \
number is higher than the camp coalition can plausibly move; a low-ranked intervention \
has cross-camp coalition support that the composite misses; mean_robustness masks a \
single-layer veto. One sentence per flag, with the specific mechanism.

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
    warrants = list_nodes(Warrant, data_dir)
    sources = list_nodes(Source, data_dir)

    rankings = rank_interventions(interventions)
    desc_convs = find_descriptive_convergences(camps)
    contested = find_contested_claims(descriptives, warrants, sources)
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
