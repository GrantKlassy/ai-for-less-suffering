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
    Evidence,
    Intervention,
    NormativeClaim,
    Source,
    Support,
)
from afls.schema.ids import content_hash, content_id
from afls.storage import list_nodes, load_node, save_node

DEFAULT_CAMP_IDS: tuple[str, ...] = (
    "camp_palantir",
    "camp_anthropic",
    "camp_operator",
    "camp_displaced_workers",
    "camp_xrisk",
)


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


class EvidenceSummary(_StrictModel):
    """Flattened evidence view for the contested-claim renderer.

    Deliberately embeds source title and stance inline so downstream consumers
    (markdown, Astro page) do not need to re-read the YAML graph to label the
    evidence. The JSON is self-contained.
    """

    evidence_id: str
    source_id: str
    source_title: str
    stance: str
    method_tag: str
    weight: float
    locator: str = ""


class ContestedClaim(_StrictModel):
    """A claim with both supporting and contradicting evidence attached.

    Computed deterministically --- no LLM involved. The presence of a contested
    claim in the analysis signals auditable disagreement, not a black-box
    confidence score.
    """

    claim_id: str
    claim_text: str
    supports: list[EvidenceSummary]
    contradicts: list[EvidenceSummary]
    qualifies: list[EvidenceSummary] = Field(default_factory=list)


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
    contested_claims: list[ContestedClaim] = Field(default_factory=list)


def find_descriptive_convergences(camps: list[Camp]) -> list[str]:
    """Descriptive claim IDs held by *every* provided camp. Sorted for determinism."""
    if not camps:
        return []
    shared = set(camps[0].held_descriptive)
    for camp in camps[1:]:
        shared &= set(camp.held_descriptive)
    return sorted(shared)


def _evidence_summary(evidence: Evidence, source_title: str) -> EvidenceSummary:
    return EvidenceSummary(
        evidence_id=evidence.id,
        source_id=evidence.source_id,
        source_title=source_title,
        stance=evidence.supports.value,
        method_tag=evidence.method_tag.value,
        weight=evidence.weight,
        locator=evidence.locator,
    )


def find_contested_claims(
    claims: list[DescriptiveClaim],
    evidence_list: list[Evidence],
    sources: list[Source],
) -> list[ContestedClaim]:
    """Claims with at least one support evidence AND at least one contradict evidence.

    Sorted by claim_id for determinism. Qualifying evidence is surfaced too --- a
    contested claim deserves the full evidence context, not just the two stances.
    """
    sources_by_id = {s.id: s for s in sources}
    evidence_by_claim: dict[str, list[Evidence]] = {}
    for evidence in evidence_list:
        evidence_by_claim.setdefault(evidence.claim_id, []).append(evidence)

    claims_by_id = {c.id: c for c in claims}
    contested: list[ContestedClaim] = []
    for claim_id in sorted(evidence_by_claim):
        claim = claims_by_id.get(claim_id)
        if claim is None:
            continue
        es = evidence_by_claim[claim_id]
        supports = [e for e in es if e.supports is Support.SUPPORT]
        contradicts = [e for e in es if e.supports is Support.CONTRADICT]
        if not supports or not contradicts:
            continue
        qualifies = [e for e in es if e.supports is Support.QUALIFY]

        def summarize(e: Evidence) -> EvidenceSummary:
            src = sources_by_id.get(e.source_id)
            title = src.title if src else "(source missing)"
            return _evidence_summary(e, title)

        contested.append(
            ContestedClaim(
                claim_id=claim.id,
                claim_text=claim.text,
                supports=[summarize(e) for e in supports],
                contradicts=[summarize(e) for e in contradicts],
                qualifies=[summarize(e) for e in qualifies],
            )
        )
    return contested


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
            lines.append(f"    - {ref}: {claim.text}")
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


def _format_descriptive_with_evidence(
    claim: DescriptiveClaim,
    evidence_list: list[Evidence],
    sources_by_id: dict[str, Source],
) -> str:
    lines = [
        f"- id: {claim.id}",
        f"  text: {claim.text}",
        f"  confidence: {claim.confidence}",
    ]
    if evidence_list:
        lines.append("  evidence:")
        for evidence in evidence_list:
            source = sources_by_id.get(evidence.source_id)
            source_title = source.title if source else "(source missing)"
            lines.append(
                f"    - [{evidence.supports.value}|{evidence.method_tag.value}|"
                f"w={evidence.weight}] {source_title} (src={evidence.source_id})"
            )
    return "\n".join(lines)


def build_graph_context(
    camps: list[Camp],
    descriptives: list[DescriptiveClaim],
    normatives: list[NormativeClaim],
    interventions: list[Intervention],
    evidence_list: list[Evidence] | None = None,
    sources: list[Source] | None = None,
) -> str:
    """Render the slice of graph state the LLM needs to reason over.

    Evidence is folded inline under each descriptive claim so the LLM sees which
    backing the confidence score is (or is not) resting on. Without this, a reader
    from camp Palantir cannot audit the reasoning --- they only see an asserted number.
    """
    claims_by_id: dict[str, DescriptiveClaim | NormativeClaim] = {}
    for desc in descriptives:
        claims_by_id[desc.id] = desc
    for norm in normatives:
        claims_by_id[norm.id] = norm
    sources_by_id = {s.id: s for s in (sources or [])}
    evidence_by_claim: dict[str, list[Evidence]] = {}
    for evidence in evidence_list or []:
        evidence_by_claim.setdefault(evidence.claim_id, []).append(evidence)

    sections = ["# Current graph (camps, claims, interventions, evidence)", "", "## Camps"]
    for camp in camps:
        sections.append(_format_camp(camp, claims_by_id))
    if evidence_list is not None:
        sections.append("\n## Descriptive claims (with evidence)")
        for desc in descriptives:
            sections.append(
                _format_descriptive_with_evidence(
                    desc, evidence_by_claim.get(desc.id, []), sources_by_id
                )
            )
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

Against the operator's priors (GRANT_BRAIN.md), flag blindspots: camps or positions the operator \
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
    evidence_list = list_nodes(Evidence, data_dir)
    sources = list_nodes(Source, data_dir)

    desc_convs = find_descriptive_convergences(camps)
    contested = find_contested_claims(descriptives, evidence_list, sources)
    context = build_graph_context(
        camps, descriptives, normatives, interventions, evidence_list, sources
    )

    llm_out = complete_and_parse(
        client,
        model_cls=PalantirLLMOutput,
        user_message=_USER_PROMPT,
        extra_context=context,
        model=model,
    )

    bridges = [
        Bridge(
            id=content_id(
                "bridge",
                slug_parts=[proposal.from_camp, "to", proposal.to_camp],
                hashed=proposal.translation,
            ),
            from_camp=proposal.from_camp,
            to_camp=proposal.to_camp,
            translation=proposal.translation,
            caveats=proposal.caveats,
            content_hash=content_hash(proposal.translation),
        )
        for proposal in llm_out.bridges
    ]
    blindspots = [
        BlindSpot(
            id=content_id(
                "blind",
                slug_parts=[proposal.flagged_camp_id],
                hashed=proposal.reasoning,
            ),
            against_prior_set="GRANT_BRAIN.md",
            flagged_camp_id=proposal.flagged_camp_id,
            reasoning=proposal.reasoning,
            content_hash=content_hash(proposal.reasoning),
        )
        for proposal in llm_out.blindspots
    ]

    return PalantirAnalysis(
        camps=[c.id for c in camps],
        descriptive_convergences=desc_convs,
        convergent_interventions=llm_out.convergent_interventions,
        bridges=bridges,
        blindspots=blindspots,
        contested_claims=contested,
    )


def persist_palantir_nodes(analysis: PalantirAnalysis, data_dir: Path) -> dict[str, int]:
    """Write any new Bridge/BlindSpot from `analysis` to `data/`. Dedupes by ID.

    Returns counts of newly-written vs skipped nodes per kind. The in-analysis
    JSON keeps the full object for snapshot integrity; the persisted YAML is
    the canonical graph node. Same translation + same camp pair → same ID, so
    re-running the query is idempotent at the graph layer.
    """
    counts = {
        "bridges_written": 0,
        "bridges_skipped": 0,
        "blindspots_written": 0,
        "blindspots_skipped": 0,
    }
    for bridge in analysis.bridges:
        try:
            load_node(Bridge, bridge.id, data_dir)
            counts["bridges_skipped"] += 1
        except FileNotFoundError:
            save_node(bridge, data_dir)
            counts["bridges_written"] += 1
    for blindspot in analysis.blindspots:
        try:
            load_node(BlindSpot, blindspot.id, data_dir)
            counts["blindspots_skipped"] += 1
        except FileNotFoundError:
            save_node(blindspot, data_dir)
            counts["blindspots_written"] += 1
    return counts
