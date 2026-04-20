"""Reallocation query.

MANIFESTO's first question is not "rank interventions" --- that's leverage.py.
It's "given the current distribution of AI effort across domains, what
reallocations would cause the greatest reduction in suffering?" A reallocation
is a *move*: shift effort from intervention A to intervention B. That needs
pair-delta ranking, not single-intervention ranking.

For every pair `(from, to)` of interventions where `to` has a strictly higher
net_composite than `from`, compute:

    delta_net = net_composite[to] - net_composite[from]

and sort descending. Pairs with non-positive `delta_net` are trivially bad
moves (shifting toward a lower-EV intervention) and are omitted from the main
ranking rather than smuggled in with a negative score.

Harm is already netted into `net_composite` via leverage.py's composite tower,
so "the destination is dirtier than the source" is not automatically flagged
--- it's already priced. But a pair whose destination has *materially* lower
harm_robustness is worth surfacing separately: the composite's multiplicative
shape means a small harm drop can be masked by a large suffering gain, and
the operator may want to see those trades explicitly. That's the
`harm_divergence_flag` list, orthogonal to the main sort.

The LLM pass layers coalition shift analysis on the top-K pairs: which camps
gain political standing under the shift, which lose, where the friction
re-binds differently from the source's friction profile. Then it flags
`reallocation_blindspots` --- pairs the composite likely mis-prices given the
camp graph.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from afls.queries.leverage import (
    LeverageRanking,
    rank_interventions,
)
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

# A drop of this magnitude in harm_robustness between source and destination
# qualifies the pair for the harm_divergence_flag list. 0.10 = 10 percentage
# points on the [0, 1] harm scale; small enough to catch real trades,
# large enough to not flood the operator with noise.
HARM_DIVERGENCE_THRESHOLD: float = 0.10

# Cap for how many top-ranked pairs the LLM is asked to reason about. The
# deterministic ranking shows all positive-delta pairs; the LLM analysis is
# gated to the top K + the flagged pairs so the prompt stays bounded.
DEFAULT_COALITION_SHIFT_K: int = 5


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReallocationPair(_StrictModel):
    """Deterministic pair-delta row. Computed from LeverageRanking rows.

    The three per-term deltas are kept alongside `delta_net` so the operator
    can see whether the move gains its value from a suffering improvement, a
    harm reduction, or both --- a pair with big `delta_suffering_composite`
    but negative `delta_harm_robustness` is a dirtier trade than a pair with
    the same `delta_net` but clean harm math.
    """

    from_intervention_id: str
    to_intervention_id: str
    from_net_composite: float
    to_net_composite: float
    delta_net: float = Field(
        description="to_net_composite - from_net_composite. Sort key. Only "
        "positive deltas enter the main `pairs` list; flagged pairs may have "
        "any delta."
    )
    delta_suffering_composite: float = Field(
        description="to_suffering_composite - from_suffering_composite. How "
        "much of the move's value is pure suffering-reduction gain (ignoring "
        "harm)."
    )
    delta_harm_robustness: float = Field(
        description="to_mean_harm_robustness - from_mean_harm_robustness. "
        "Negative means the destination is harm-dirtier than the source; "
        "positive means cleaner. Flagged when below -HARM_DIVERGENCE_THRESHOLD."
    )
    delta_viability: float = Field(
        description="to_composite_score - from_composite_score. How much of "
        "the move is pure viability (leverage x friction) change."
    )


class ReallocationCoalitionShift(_StrictModel):
    """Per-pair LLM output: who gains, who loses, how friction re-binds.

    Not persisted as graph nodes. Ephemeral to the analysis, same as
    RankingBlindSpot in leverage.py.
    """

    from_intervention_id: str
    to_intervention_id: str
    gaining_camps: list[str] = Field(
        default_factory=list,
        description="Camps whose political standing or coalition leverage "
        "strengthens under this shift.",
    )
    losing_camps: list[str] = Field(
        default_factory=list,
        description="Camps that lose standing or whose veto becomes harder to "
        "sustain. Not merely camps indifferent to the shift.",
    )
    friction_rebinds: str = Field(
        min_length=1,
        description="One paragraph, operator voice, on (a) where friction "
        "binds differently at the destination vs. the source, and (b) "
        "whether the harm trade-off is real or a scoring artifact.",
    )


class ReallocationBlindSpot(_StrictModel):
    """Flag that a pair's delta_net is suspected to mis-price the move.

    Distinct from `schema.BlindSpot` (which targets camps) and from
    `RankingBlindSpot` in leverage.py (which targets single interventions).
    Reallocation blindspots target pairs.
    """

    flagged_from_intervention_id: str
    flagged_to_intervention_id: str
    reasoning: str = Field(
        min_length=1,
        description="One sentence on the specific mechanism: why the "
        "composite-ranked delta_net over- or under-sells this move.",
    )


class ReallocationLLMOutput(_StrictModel):
    """Complete schema the LLM must return for the reallocation query."""

    coalition_shifts: list[ReallocationCoalitionShift] = Field(default_factory=list)
    reallocation_blindspots: list[ReallocationBlindSpot] = Field(default_factory=list)


class ReallocationAnalysis(BaseModel):
    """Canonical output written to `public-output/analyses/reallocation_<stamp>.json`."""

    model_config = ConfigDict(extra="forbid")

    kind: ClassVar[str] = "reallocation_analysis"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    camps: list[str]
    descriptive_convergences: list[str]
    rankings: list[LeverageRanking] = Field(
        description="Full single-intervention ranking table, carried through "
        "so the reader can map each pair's endpoints back to their base "
        "composite scores without leaving the page."
    )
    pairs: list[ReallocationPair] = Field(
        description="All pairs with positive delta_net, sorted descending. "
        "Trivially-bad moves (non-positive delta_net) are omitted."
    )
    harm_divergence_flags: list[ReallocationPair] = Field(
        default_factory=list,
        description="Orthogonal list: pairs (positive or negative delta_net) "
        "whose delta_harm_robustness is below -HARM_DIVERGENCE_THRESHOLD. A "
        "pair can appear in both `pairs` and this list --- gaining suffering "
        "reduction at a material harm cost is the exact trade the operator "
        "needs to see explicitly.",
    )
    coalition_shifts: list[ReallocationCoalitionShift] = Field(default_factory=list)
    reallocation_blindspots: list[ReallocationBlindSpot] = Field(default_factory=list)
    contested_claims: list[ContestedClaim] = Field(default_factory=list)


def compute_reallocation_pairs(
    rankings: list[LeverageRanking],
) -> tuple[list[ReallocationPair], list[ReallocationPair]]:
    """Cartesian pair-delta over rankings. Returns (positive_pairs, harm_flagged).

    positive_pairs:  delta_net > 0, sorted by delta_net descending, id tiebreak.
    harm_flagged:    delta_harm_robustness < -HARM_DIVERGENCE_THRESHOLD, sorted
                     by delta_harm_robustness ascending (worst first).
    """
    positive: list[ReallocationPair] = []
    flagged: list[ReallocationPair] = []
    for source in rankings:
        for dest in rankings:
            if source.intervention_id == dest.intervention_id:
                continue
            delta_net = dest.net_composite - source.net_composite
            delta_harm = dest.mean_harm_robustness - source.mean_harm_robustness
            pair = ReallocationPair(
                from_intervention_id=source.intervention_id,
                to_intervention_id=dest.intervention_id,
                from_net_composite=source.net_composite,
                to_net_composite=dest.net_composite,
                delta_net=delta_net,
                delta_suffering_composite=dest.suffering_composite
                - source.suffering_composite,
                delta_harm_robustness=delta_harm,
                delta_viability=dest.composite_score - source.composite_score,
            )
            if delta_net > 0:
                positive.append(pair)
            if delta_harm < -HARM_DIVERGENCE_THRESHOLD:
                flagged.append(pair)
    positive.sort(
        key=lambda p: (-p.delta_net, p.from_intervention_id, p.to_intervention_id)
    )
    flagged.sort(
        key=lambda p: (
            p.delta_harm_robustness,
            p.from_intervention_id,
            p.to_intervention_id,
        )
    )
    return positive, flagged


def _format_pair(pair: ReallocationPair) -> str:
    harm_note = (
        f" [HARM FLAG: delta_harm_robustness={pair.delta_harm_robustness:.3f}]"
        if pair.delta_harm_robustness < -HARM_DIVERGENCE_THRESHOLD
        else ""
    )
    return (
        f"- {pair.from_intervention_id} -> {pair.to_intervention_id}: "
        f"delta_net={pair.delta_net:+.3f}{harm_note}\n"
        f"    from_net={pair.from_net_composite:.3f}, "
        f"to_net={pair.to_net_composite:.3f}\n"
        f"    delta_suffering_composite={pair.delta_suffering_composite:+.3f}, "
        f"delta_harm_robustness={pair.delta_harm_robustness:+.3f}, "
        f"delta_viability={pair.delta_viability:+.3f}"
    )


def _format_camp_terse(camp: Camp) -> str:
    held = ", ".join(camp.held_descriptive[:6])
    norms = ", ".join(camp.held_normative)
    return (
        f"- id: {camp.id} | name: {camp.name}\n"
        f"  summary: {camp.summary}\n"
        f"  held_descriptive (first 6): {held}\n"
        f"  held_normative: {norms}"
    )


def _format_ranking_row_terse(row: LeverageRanking) -> str:
    return (
        f"- {row.intervention_id}: net={row.net_composite:.3f} "
        f"(suffering={row.suffering_composite:.3f}, "
        f"harm_robustness={row.mean_harm_robustness:.3f}, "
        f"viability={row.composite_score:.3f})"
    )


def build_reallocation_context(
    camps: list[Camp],
    rankings: list[LeverageRanking],
    coalition_pairs: list[ReallocationPair],
    harm_flagged: list[ReallocationPair],
    descriptives: list[DescriptiveClaim],
    normatives: list[NormativeClaim],
) -> str:
    """Render the graph slice the LLM needs for coalition_shifts + blindspot reasoning."""
    claims_by_id: dict[str, DescriptiveClaim | NormativeClaim] = {}
    for d in descriptives:
        claims_by_id[d.id] = d
    for n in normatives:
        claims_by_id[n.id] = n

    sections = [
        "# Reallocation analysis (deterministic deltas) + camp registry",
        "",
        "Harm and friction share polarity: 1 = no harm / no friction, "
        "0 = maximum harm / fully blocked. Suffering: 1 = maximum reduction, "
        "0 = none. net_composite = leverage x mean(friction) x "
        "mean(suffering_reduction) x mean(harm_robustness).",
        "",
        "A reallocation pair (from -> to) represents shifting AI effort from "
        "the source intervention to the destination. delta_net > 0 means the "
        "move gains -SUFFERING EV net of harm; delta_harm_robustness < 0 "
        "means the destination is dirtier than the source (a harm trade that "
        "the composite has already priced in but the operator may want to see "
        "called out). Pairs with delta_harm_robustness below "
        f"-{HARM_DIVERGENCE_THRESHOLD} are in the harm_divergence_flags list.",
        "",
        "## Intervention rankings (single-intervention, for reference)",
    ]
    for row in rankings:
        sections.append(_format_ranking_row_terse(row))

    sections.append(
        f"\n## Top {len(coalition_pairs)} reallocation pairs (positive delta_net)"
    )
    if not coalition_pairs:
        sections.append("(no pairs with positive delta_net)")
    for pair in coalition_pairs:
        sections.append(_format_pair(pair))

    sections.append("\n## Harm-divergence flagged pairs")
    sections.append(
        f"Pairs where delta_harm_robustness < -{HARM_DIVERGENCE_THRESHOLD}. Can "
        "overlap with the positive-delta_net list above; a pair in both is a "
        "suffering-gain-at-harm-cost trade.",
    )
    if not harm_flagged:
        sections.append("(no harm-divergence flagged pairs)")
    for pair in harm_flagged:
        sections.append(_format_pair(pair))

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


_USER_PROMPT = """Analyze these reallocation pairs and the camps.

The pair deltas are deterministic --- delta_net = to_net_composite - \
from_net_composite. Harm is already netted into both endpoints. Do not \
second-guess the numbers; reason about the coalitions around the moves and \
the plausibility of the trades.

For each pair in the 'Top N reallocation pairs' section (and only those \
pairs), return a `coalition_shifts` entry:
- `from_intervention_id` and `to_intervention_id`: exactly as given
- `gaining_camps`: camps whose coalition leverage or political standing \
strengthens under the shift. Not merely camps who prefer the destination over \
the source --- camps whose veto becomes harder to sustain, whose normative \
stack is better served, or whose coalition partners are more numerous at the \
destination.
- `losing_camps`: camps actively worsened by the move (not indifferent). \
Especially relevant for pairs in the harm_divergence_flags list, where harm-\
side camps (environmentalists, displaced workers, concentration-wary) \
typically lose standing.
- `friction_rebinds`: one paragraph, operator voice, on (a) where friction \
binds differently at the destination compared to the source, and (b) \
whether the harm trade-off is real or a scoring artifact. No hedging, no \
manifesto voice.

Then flag `reallocation_blindspots` --- pairs whose delta_net is likely \
mis-priced given the camp graph. Examples of valid flags:
- The destination's net_composite over-sells the move because the camps that \
would veto the deployment aren't in the analyzed set.
- A pair in harm_divergence_flags has delta_net > 0 but the averaged harm_\
robustness masks a catastrophic single-layer harm at the destination.
- The source intervention is *enabling* infrastructure (zero or low suffering \
numerator) whose removal would collapse the destination's friction \
robustness, and the deterministic delta doesn't see that dependency.
- The destination's mean_suffering_reduction over-counts by including a layer \
the intervention doesn't actually touch.

One sentence per flag, with the specific mechanism. Cite pair endpoints by id.

Return ONLY JSON matching the schema in the system prompt."""


def run_reallocation_query(
    client: AnthropicClient,
    data_dir: Path,
    *,
    camp_ids: tuple[str, ...] = DEFAULT_CAMP_IDS,
    model: Model = Model.OPUS,
    coalition_shift_k: int = DEFAULT_COALITION_SHIFT_K,
) -> ReallocationAnalysis:
    """Load graph, rank interventions, compute pair-deltas, ask LLM, assemble."""
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
    positive_pairs, harm_flagged = compute_reallocation_pairs(rankings)
    top_pairs = positive_pairs[:coalition_shift_k]
    desc_convs = find_descriptive_convergences(camps)
    contested = find_contested_claims(descriptives, evidence_list, sources)
    context = build_reallocation_context(
        camps, rankings, top_pairs, harm_flagged, descriptives, normatives
    )

    llm_out = complete_and_parse(
        client,
        model_cls=ReallocationLLMOutput,
        user_message=_USER_PROMPT,
        extra_context=context,
        model=model,
    )

    return ReallocationAnalysis(
        camps=[c.id for c in camps],
        descriptive_convergences=desc_convs,
        rankings=rankings,
        pairs=positive_pairs,
        harm_divergence_flags=harm_flagged,
        coalition_shifts=llm_out.coalition_shifts,
        reallocation_blindspots=llm_out.reallocation_blindspots,
        contested_claims=contested,
    )
