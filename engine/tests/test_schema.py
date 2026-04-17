"""Schema tests: construction, strict validation, round-trip through dict."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from afls.schema import (
    AxiomFamily,
    BlindSpot,
    Bridge,
    Camp,
    Convergence,
    DescriptiveClaim,
    FrictionLayer,
    Intervention,
    InterventionKind,
    NormativeClaim,
    new_id,
    slug_id,
)


def test_new_id_shape() -> None:
    ident = new_id("desc")
    assert ident.startswith("desc_")
    assert len(ident) == 5 + 6


def test_slug_id_normalizes() -> None:
    assert slug_id("camp", "Palantir Technologies") == "camp_palantir-technologies"
    assert slug_id("friction", "Public Backlash!") == "friction_public-backlash"


def test_slug_id_rejects_empty() -> None:
    with pytest.raises(ValueError):
        slug_id("camp", "   ")


def test_descriptive_claim_valid() -> None:
    claim = DescriptiveClaim(
        id=new_id("desc"),
        text="AI deployment is accelerating.",
        sources=["https://epoch.ai"],
        confidence=0.9,
        evidence=["Epoch AI compute estimates Q1 2026"],
    )
    assert claim.kind == "descriptive_claim"
    assert claim.confidence == 0.9


def test_descriptive_claim_rejects_bad_confidence() -> None:
    with pytest.raises(ValidationError):
        DescriptiveClaim(id=new_id("desc"), text="x", confidence=1.5)


def test_descriptive_claim_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        DescriptiveClaim(
            id=new_id("desc"),
            text="x",
            confidence=0.5,
            smuggled_value="should not be allowed",  # type: ignore[call-arg]
        )


def test_normative_claim_requires_axiom_family() -> None:
    claim = NormativeClaim(
        id=new_id("norm"),
        text="AI compute should be pointed at suffering reduction.",
        axiom_family=AxiomFamily.EA_80K,
        axiom_detail="80,000 Hours-style prioritization.",
    )
    assert claim.axiom_family is AxiomFamily.EA_80K


def test_normative_claim_accepts_all_axiom_families() -> None:
    for family in AxiomFamily:
        NormativeClaim(id=new_id("norm"), text="x", axiom_family=family)


def test_camp_holds_claim_refs() -> None:
    camp = Camp(
        id=slug_id("camp", "Palantir"),
        name="Palantir",
        agents=["Palantir Technologies Inc."],
        held_descriptive=["desc_abc123"],
        held_normative=["norm_def456"],
        summary="Defense/intelligence AI contractor.",
    )
    assert camp.id == "camp_palantir"
    assert camp.held_descriptive == ["desc_abc123"]


def test_intervention_scored_against_frictions() -> None:
    intervention = Intervention(
        id=new_id("intv"),
        text="Expand frontier-lab headcount.",
        action_kind=InterventionKind.ECONOMIC,
        cost_estimate="$10B over 5 years",
        leverage_score=0.7,
        friction_scores={"friction_capex": 0.6, "friction_regulation": 0.8},
    )
    assert intervention.action_kind is InterventionKind.ECONOMIC
    assert intervention.friction_scores["friction_capex"] == 0.6


def test_friction_layer_basic() -> None:
    layer = FrictionLayer(
        id=slug_id("friction", "grid"),
        name="grid",
        description="Electrical grid capacity.",
    )
    assert layer.id == "friction_grid"


def test_bridge_requires_both_sides() -> None:
    bridge = Bridge(
        id=new_id("bridge"),
        from_camp="camp_palantir",
        to_camp="camp_anthropic",
        translation=(
            "'Mission-critical deployment' in defense framing maps to "
            "'responsible scaling' in lab framing."
        ),
        caveats=["Does not translate on autonomous-weapons question."],
    )
    assert bridge.from_camp == "camp_palantir"


def test_convergence_requires_two_camps() -> None:
    conv = Convergence(
        id=new_id("conv"),
        intervention_id="intv_abc123",
        camps=["camp_palantir", "camp_anthropic"],
        divergent_reasons={
            "camp_palantir": "norm_contract_revenue",
            "camp_anthropic": "norm_responsible_scaling",
        },
    )
    assert len(conv.camps) == 2


def test_convergence_rejects_single_camp() -> None:
    with pytest.raises(ValidationError):
        Convergence(
            id=new_id("conv"),
            intervention_id="intv_abc123",
            camps=["camp_palantir"],
        )


def test_blindspot_requires_reasoning() -> None:
    spot = BlindSpot(
        id=new_id("blind"),
        against_prior_set="grant",
        flagged_camp_id="camp_displaced_workers",
        reasoning="Operator's default accelerationism under-weights labor-displacement camp.",
    )
    assert spot.against_prior_set == "grant"


@pytest.mark.parametrize(
    "model_factory",
    [
        lambda: DescriptiveClaim(id=new_id("desc"), text="x", confidence=0.5),
        lambda: NormativeClaim(id=new_id("norm"), text="x", axiom_family=AxiomFamily.POKER_EV),
        lambda: Camp(id=slug_id("camp", "Anthropic"), name="Anthropic"),
        lambda: Intervention(
            id=new_id("intv"),
            text="x",
            action_kind=InterventionKind.TECHNICAL,
            leverage_score=0.5,
        ),
        lambda: FrictionLayer(id=slug_id("friction", "capex"), name="capex"),
        lambda: Bridge(
            id=new_id("bridge"),
            from_camp="camp_a",
            to_camp="camp_b",
            translation="x",
        ),
        lambda: Convergence(
            id=new_id("conv"),
            intervention_id="intv_x",
            camps=["camp_a", "camp_b"],
        ),
        lambda: BlindSpot(
            id=new_id("blind"),
            against_prior_set="grant",
            flagged_camp_id="camp_x",
            reasoning="x",
        ),
    ],
)
def test_round_trip_through_dict(model_factory: object) -> None:
    """Every node must dict-serialize and rebuild identically --- required for YAML storage."""
    original = model_factory()  # type: ignore[operator]
    payload = original.model_dump(mode="json")
    rebuilt = type(original).model_validate(payload)
    assert rebuilt.model_dump(mode="json") == payload
