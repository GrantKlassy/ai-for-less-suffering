"""Leverage query.

Ranks interventions by
`leverage_score x mean(friction_scores) x mean(harm_scores) x mean(suffering_reduction_scores)`.
The ranking is deterministic and operator-authored --- the LLM does not invent
leverage, friction, harm, or suffering-reduction numbers. One Opus pass layers
coalition analysis per ranked intervention: which camps line up, which contest
it, what the expected friction fight looks like, and whether the suffering
numerator is plausible.

Friction and harm share polarity (1 = no friction / no harm, 0 = fully blocked
/ maximum harm), so both multiply in without sign flips. An intervention that
reduces disease suffering but imposes heavy water/land/displacement/lock-in
costs scores below a clean one --- this is the directive's read of "suffering
caused by AI" baked into the composite, not a post-hoc adjustment.

Interventions with zero suffering_reduction_scores rank zero regardless of
political viability; that is intentional. The old composites (`viability =
leverage x robustness` and `suffering_composite = viability x suffering`) are
kept alongside so the marginal effect of each term on the ranking is legible.
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

    Three composites, each a superset of the last so the marginal effect of
    each term is legible:
    - `composite_score`    = leverage x robustness              (viability)
    - `suffering_composite`= viability x mean_suffering_reduction (-SUFFERING EV)
    - `net_composite`      = suffering_composite x mean_harm_robustness
                             (-SUFFERING EV net of harm caused if it lands)

    Rankings sort by `net_composite`. An intervention that cleanly reduces
    suffering with low harm outranks one that reduces the same suffering while
    imposing water/land/displacement costs.
    """

    intervention_id: str
    intervention_text: str
    leverage_score: float
    mean_robustness: float = Field(
        description="Mean of friction_scores values. Friction semantic: 1 = no "
        "friction, 0 = fully blocked. Higher is better."
    )
    mean_harm_robustness: float = Field(
        description="Mean of harm_scores values. Harm semantic: 1 = no harm, "
        "0 = maximum harm (same polarity as friction). Zero when scores are "
        "absent --- absent harm scores collapse net_composite to zero by "
        "design, the same way absent suffering scores do."
    )
    mean_suffering_reduction: float = Field(
        description="Mean of suffering_reduction_scores values. Suffering "
        "semantic: 1 = maximum reduction, 0 = no reduction. Zero when scores "
        "are absent --- no suffering-reduction numerator, no -SUFFERING EV."
    )
    composite_score: float = Field(
        description="Viability: leverage_score x mean_robustness. Ignores what "
        "the intervention is pointed at and what it costs to get there."
    )
    suffering_composite: float = Field(
        description="-SUFFERING EV (gross): composite_score x "
        "mean_suffering_reduction. Ignores harm caused if the intervention lands."
    )
    net_composite: float = Field(
        description="-SUFFERING EV (net of harm): suffering_composite x "
        "mean_harm_robustness. Rankings sort by this."
    )
    friction_scores: dict[str, float]
    harm_scores: dict[str, float] = Field(default_factory=dict)
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


def _mean_harm_robustness(intervention: Intervention) -> float:
    scores = list(intervention.harm_scores.values())
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _mean_suffering_reduction(intervention: Intervention) -> float:
    scores = list(intervention.suffering_reduction_scores.values())
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def rank_interventions(interventions: list[Intervention]) -> list[LeverageRanking]:
    """Deterministic ranking: net_composite descending, id as tie-break."""
    rows: list[LeverageRanking] = []
    for intv in interventions:
        robustness = _mean_robustness(intv)
        harm_robustness = _mean_harm_robustness(intv)
        suffering = _mean_suffering_reduction(intv)
        composite = intv.leverage_score * robustness
        suffering_composite = composite * suffering
        rows.append(
            LeverageRanking(
                intervention_id=intv.id,
                intervention_text=intv.text,
                leverage_score=intv.leverage_score,
                mean_robustness=robustness,
                mean_harm_robustness=harm_robustness,
                mean_suffering_reduction=suffering,
                composite_score=composite,
                suffering_composite=suffering_composite,
                net_composite=suffering_composite * harm_robustness,
                friction_scores=dict(intv.friction_scores),
                harm_scores=dict(intv.harm_scores),
                suffering_reduction_scores=dict(intv.suffering_reduction_scores),
            )
        )
    rows.sort(key=lambda r: (-r.net_composite, r.intervention_id))
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
    harm = ", ".join(f"{k}={v}" for k, v in sorted(row.harm_scores.items()))
    suffering = ", ".join(
        f"{k}={v}" for k, v in sorted(row.suffering_reduction_scores.items())
    )
    return (
        f"- {row.intervention_id}: net_composite={row.net_composite:.3f} "
        f"(suffering_composite={row.suffering_composite:.3f} x "
        f"harm_robustness={row.mean_harm_robustness:.3f})\n"
        f"    suffering_composite = viability={row.composite_score:.3f} x "
        f"suffering={row.mean_suffering_reduction:.3f}\n"
        f"    viability = leverage={row.leverage_score} x "
        f"robustness={row.mean_robustness:.3f}\n"
        f"    text: {row.intervention_text}\n"
        f"    friction_scores: {friction}\n"
        f"    harm_scores: {harm or '(none)'}\n"
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
        "Harm semantic: 1 = no harm, 0 = maximum harm. Same polarity as friction. "
        "Absence of harm_scores => zero net_composite by design.",
        "Suffering-reduction semantic: 1 = maximum reduction, 0 = no reduction. "
        "Absence of scores => zero net_composite by design.",
        "",
        "Composites (nested so each term's marginal effect stays legible):",
        "  viability            = leverage x mean(friction)",
        "  suffering_composite  = viability x mean(suffering_reduction)",
        "  net_composite        = suffering_composite x mean(harm_robustness)",
        "Rankings sort by net_composite --- the -SUFFERING EV net of harm caused "
        "if the intervention lands.",
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

The ranking is deterministic --- net_composite = \
leverage x mean(friction) x mean(suffering_reduction) x mean(harm_robustness). \
Do not second-guess the numbers; reason about the coalitions around them and \
the plausibility of the suffering numerator and the harm scores.

For each intervention in the ranking, return a `coalition_analyses` entry:
- `supporting_camps`: camps whose normative stack + held descriptives line up behind it
- `contesting_camps`: camps whose stance actively opposes or constrains it (not merely \
indifferent). Harm-side camps (environmentalists, displaced-workers, concentration-\
wary) often sit here on interventions whose harm_scores are low.
- `expected_friction`: one paragraph on (a) where the friction actually binds in \
practice, (b) whether the suffering_reduction_scores look right given the \
intervention's mechanism, and (c) whether the harm_scores look right --- \
especially if an intervention is ranked high on net_composite but has obvious \
water/land/displacement/concentration costs that the scores under-count. \
Operator voice: specific, no hedging, no manifesto voice, name the binding \
constraint, name the suffering layer the intervention actually touches, and \
name the harm layer if the scores look off.

Then flag `ranking_blindspots` --- interventions whose net_composite is likely \
mispriced given the camp graph, the suffering layers, or the harm layers. \
Examples of valid flags: the operator's leverage is higher than the camp \
coalition can plausibly move; a low-ranked intervention has cross-camp \
coalition support that the composite misses; mean_robustness masks a \
single-layer veto; mean_harm_robustness masks a catastrophic single-layer harm \
(e.g. one harm_score near zero averaged against several near one); a \
suffering_reduction_scores entry credits an intervention for a layer it \
doesn't actually touch; harm_scores under-count a first-order cost (water, \
displacement, concentration, lock-in) that the intervention's mechanism \
obviously incurs; an intervention with zero suffering numerator is ranked at \
the bottom when its *enabling* role for suffering-reducing deployment is \
load-bearing. One sentence per flag, with the specific mechanism.

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
