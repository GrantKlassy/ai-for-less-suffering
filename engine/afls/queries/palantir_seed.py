"""Seed data for the Palantir coalition query.

Running this module populates `data/` with the baseline graph: three camps (Palantir,
Anthropic, Operator-aligned) plus the descriptive/normative claims, interventions, and
friction layers that make the Palantir test query meaningful.

Seed data is the *starting point* --- the operator curates via `afls edit` and `afls add`
from there. Re-running this module overwrites with the baseline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from afls.config import data_dir
from afls.schema import (
    AxiomFamily,
    BaseNode,
    Camp,
    DescriptiveClaim,
    FrictionLayer,
    Intervention,
    InterventionKind,
    MethodTag,
    NormativeClaim,
    Source,
    SourceKind,
    Support,
    Warrant,
)
from afls.storage import save_node

FIXED_TS = datetime(2026, 4, 17, 0, 0, 0, tzinfo=UTC)


def _stamp(node: BaseNode) -> BaseNode:
    """Set deterministic timestamps so YAML diffs stay stable across reseeds."""
    node.created_at = FIXED_TS
    node.updated_at = FIXED_TS
    return node


def _descriptive_claims() -> list[DescriptiveClaim]:
    return [
        DescriptiveClaim(
            id="desc_accelerating",
            text="AI capability is accelerating along compute, data, and algorithmic axes.",
            confidence=0.9,
        ),
        DescriptiveClaim(
            id="desc_compute_matters",
            text="Frontier AI performance scales with compute and capex.",
            confidence=0.9,
        ),
        DescriptiveClaim(
            id="desc_grid_constraint",
            text="Electricity generation and transmission are near-term bottlenecks for "
            "datacenter buildout.",
            confidence=0.8,
        ),
        DescriptiveClaim(
            id="desc_us_lead",
            text="The US currently leads China in frontier AI by roughly 6-18 months.",
            confidence=0.6,
        ),
        DescriptiveClaim(
            id="desc_enterprise_slow",
            text="Enterprise and government absorption of AI capability lags the frontier by "
            "years, not months.",
            confidence=0.75,
        ),
    ]


def _sources() -> list[Source]:
    return [
        Source(
            id="src_epoch_ai",
            source_kind=SourceKind.DASHBOARD,
            title="Epoch AI --- compute, data, and algorithmic trends",
            url="https://epoch.ai",
            authors=["Epoch AI research team"],
            published_at="ongoing",
            reliability=0.85,
            notes="Public dashboard tracking frontier-model compute and data scaling. "
            "Primary operator reference.",
        ),
        Source(
            id="src_semianalysis",
            source_kind=SourceKind.BLOG,
            title="SemiAnalysis --- compute, capex, and datacenter analysis",
            url="https://semianalysis.com",
            authors=["Dylan Patel et al."],
            published_at="ongoing",
            reliability=0.7,
            notes="Industry-adjacent analysis. Strong on supply-chain specifics; "
            "not peer-reviewed.",
        ),
    ]


def _warrants() -> list[Warrant]:
    return [
        Warrant(
            id="war_epoch_accelerating",
            claim_id="desc_accelerating",
            source_id="src_epoch_ai",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="trends dashboard",
        ),
        Warrant(
            id="war_epoch_compute_matters",
            claim_id="desc_compute_matters",
            source_id="src_epoch_ai",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.85,
            locator="compute-vs-performance section",
        ),
        Warrant(
            id="war_semi_compute_matters",
            claim_id="desc_compute_matters",
            source_id="src_semianalysis",
            method_tag=MethodTag.TRIANGULATION,
            supports=Support.SUPPORT,
            weight=0.7,
            locator="capex and cluster analyses",
        ),
    ]


def _normative_claims() -> list[NormativeClaim]:
    return [
        NormativeClaim(
            id="norm_palantir_national",
            text="AI should preserve and extend US national-security advantage.",
            axiom_family=AxiomFamily.CONSEQUENTIALIST,
            axiom_detail="Realist / state-capacity framing; outcomes judged by geopolitical "
            "position.",
        ),
        NormativeClaim(
            id="norm_palantir_order",
            text="Order is a precondition for freedom; institutions must be robust before they "
            "can be generous.",
            axiom_family=AxiomFamily.OTHER,
            axiom_detail="Hobbesian / order-first framing.",
        ),
        NormativeClaim(
            id="norm_anthropic_safety",
            text="AI should be developed safely by responsible actors before less cautious "
            "actors build it.",
            axiom_family=AxiomFamily.CONSEQUENTIALIST,
            axiom_detail="Safety-through-lead framing.",
        ),
        NormativeClaim(
            id="norm_anthropic_alignment",
            text="Alignment of frontier systems is the dominant catastrophic risk; capability "
            "must not outrun it.",
            axiom_family=AxiomFamily.EA_80K,
            axiom_detail="AI-safety-industry framing with catastrophic-risk weighting.",
        ),
        NormativeClaim(
            id="norm_operator_flourishing",
            text="AI should widen human flourishing broadly, not concentrate power in a few "
            "actors.",
            axiom_family=AxiomFamily.OTHER,
            axiom_detail="Distribution-of-benefit framing.",
        ),
        NormativeClaim(
            id="norm_operator_sovereignty",
            text="AI deployment should expand individual capacity rather than erode it.",
            axiom_family=AxiomFamily.OTHER,
            axiom_detail="Sovereign-individual framing.",
        ),
    ]


def _friction_layers() -> list[FrictionLayer]:
    return [
        FrictionLayer(
            id="friction_grid",
            name="Grid",
            description="Electricity generation, transmission, and interconnection capacity.",
        ),
        FrictionLayer(
            id="friction_capex",
            name="Capex",
            description="Capital availability for compute and infrastructure.",
        ),
        FrictionLayer(
            id="friction_regulation",
            name="Regulation",
            description="Political and regulatory resistance (federal, state, international).",
        ),
        FrictionLayer(
            id="friction_enterprise",
            name="Enterprise absorption",
            description="Speed at which enterprises and governments integrate AI capability.",
        ),
        FrictionLayer(
            id="friction_public",
            name="Public backlash",
            description="Labor-market disruption, cultural resistance, and political blowback.",
        ),
    ]


def _interventions() -> list[Intervention]:
    return [
        Intervention(
            id="intv_compute",
            text="Expand frontier-lab compute capacity (chips, datacenters, networking).",
            action_kind=InterventionKind.ECONOMIC,
            cost_estimate="Tens of billions annually across the industry.",
            leverage_score=0.85,
            friction_scores={
                "friction_grid": 0.4,
                "friction_capex": 0.6,
                "friction_regulation": 0.7,
                "friction_enterprise": 0.9,
                "friction_public": 0.7,
            },
        ),
        Intervention(
            id="intv_grid",
            text="Accelerate grid and generation buildout (permitting reform, interconnection, "
            "new generation).",
            action_kind=InterventionKind.POLITICAL,
            cost_estimate="Hundreds of billions federal + state; multi-decade.",
            leverage_score=0.75,
            friction_scores={
                "friction_grid": 0.5,
                "friction_capex": 0.6,
                "friction_regulation": 0.3,
                "friction_enterprise": 0.8,
                "friction_public": 0.6,
            },
        ),
        Intervention(
            id="intv_training",
            text="Invest in AI workforce training and retraining programs.",
            action_kind=InterventionKind.POLITICAL,
            cost_estimate="Single-digit billions annually.",
            leverage_score=0.35,
            friction_scores={
                "friction_grid": 1.0,
                "friction_capex": 0.8,
                "friction_regulation": 0.7,
                "friction_enterprise": 0.5,
                "friction_public": 0.8,
            },
        ),
        Intervention(
            id="intv_alignment_research",
            text="Scale funding for interpretability and alignment research.",
            action_kind=InterventionKind.ECONOMIC,
            cost_estimate="Hundreds of millions to low billions annually.",
            leverage_score=0.6,
            friction_scores={
                "friction_grid": 1.0,
                "friction_capex": 0.7,
                "friction_regulation": 0.8,
                "friction_enterprise": 0.7,
                "friction_public": 0.9,
            },
        ),
    ]


def _camps() -> list[Camp]:
    return [
        Camp(
            id="camp_palantir",
            name="Palantir",
            agents=["Palantir Technologies", "allied DoD contractors"],
            summary="Government/defense AI contractor. National-advantage framing; "
            "order-first; enterprise absorption is the gap they close.",
            held_descriptive=[
                "desc_accelerating",
                "desc_compute_matters",
                "desc_grid_constraint",
                "desc_us_lead",
                "desc_enterprise_slow",
            ],
            held_normative=["norm_palantir_national", "norm_palantir_order"],
        ),
        Camp(
            id="camp_anthropic",
            name="Anthropic",
            agents=["Anthropic", "allied frontier labs with safety orientation"],
            summary="Frontier lab with alignment orientation. Build capability safely before "
            "others do.",
            held_descriptive=[
                "desc_accelerating",
                "desc_compute_matters",
                "desc_grid_constraint",
                "desc_us_lead",
            ],
            held_normative=["norm_anthropic_safety", "norm_anthropic_alignment"],
        ),
        Camp(
            id="camp_operator",
            name="Operator-aligned",
            agents=["operator prior set"],
            summary="Starting point for the operator's frame. Refine via BRAIN.md and "
            "`afls edit camp_operator`.",
            held_descriptive=[
                "desc_accelerating",
                "desc_compute_matters",
                "desc_grid_constraint",
                "desc_enterprise_slow",
            ],
            held_normative=["norm_operator_flourishing", "norm_operator_sovereignty"],
        ),
    ]


def seed(target_dir: Path | None = None) -> int:
    """Write every seed node to `target_dir` (default: the repo data dir). Returns count."""
    root = target_dir or data_dir()
    nodes: list[BaseNode] = []
    nodes.extend(_descriptive_claims())
    nodes.extend(_normative_claims())
    nodes.extend(_friction_layers())
    nodes.extend(_interventions())
    nodes.extend(_camps())
    nodes.extend(_sources())
    nodes.extend(_warrants())
    for node in nodes:
        save_node(_stamp(node), root)
    return len(nodes)


def main() -> None:
    count = seed()
    print(f"seeded {count} nodes -> {data_dir()}")


if __name__ == "__main__":
    main()
