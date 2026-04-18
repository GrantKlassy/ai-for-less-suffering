"""Schema tests: construction, strict validation, round-trip through dict."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from afls.schema import (
    BlindSpot,
    Bridge,
    Camp,
    Convergence,
    DescriptiveClaim,
    FrictionLayer,
    HarmLayer,
    Intervention,
    InterventionKind,
    MethodTag,
    NormativeClaim,
    Source,
    SourceKind,
    SufferingLayer,
    Support,
    Warrant,
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
        confidence=0.9,
    )
    assert claim.kind == "descriptive_claim"
    assert claim.confidence == 0.9


def test_descriptive_claim_rejects_legacy_sources_field() -> None:
    with pytest.raises(ValidationError):
        DescriptiveClaim(
            id=new_id("desc"),
            text="x",
            confidence=0.5,
            sources=["https://epoch.ai"],  # type: ignore[call-arg]
        )


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


def test_normative_claim_basic() -> None:
    claim = NormativeClaim(
        id=new_id("norm"),
        text="AI compute should be pointed at suffering reduction.",
    )
    assert claim.kind == "normative_claim"
    assert claim.text.startswith("AI compute")


def test_normative_claim_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        NormativeClaim(
            id=new_id("norm"),
            text="x",
            axiom_family="ea_80k",  # type: ignore[call-arg]
        )


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


def test_intervention_scored_against_harms() -> None:
    intervention = Intervention(
        id=new_id("intv"),
        text="Expand training compute.",
        action_kind=InterventionKind.ECONOMIC,
        leverage_score=0.7,
        harm_scores={"harm_water": 0.3, "harm_extraction": 0.5},
    )
    assert intervention.harm_scores["harm_water"] == 0.3
    assert intervention.harm_scores["harm_extraction"] == 0.5


def test_intervention_harm_scores_default_empty() -> None:
    intervention = Intervention(
        id=new_id("intv"),
        text="x",
        action_kind=InterventionKind.TECHNICAL,
        leverage_score=0.5,
    )
    assert intervention.harm_scores == {}


def test_friction_layer_basic() -> None:
    layer = FrictionLayer(
        id=slug_id("friction", "grid"),
        name="grid",
        description="Electrical grid capacity.",
    )
    assert layer.id == "friction_grid"


def test_harm_layer_basic() -> None:
    layer = HarmLayer(
        id=slug_id("harm", "water"),
        name="water",
        description="Datacenter freshwater consumption.",
    )
    assert layer.id == "harm_water"
    assert layer.kind == "harm_layer"


def test_harm_layer_requires_name() -> None:
    with pytest.raises(ValidationError):
        HarmLayer(id="harm_empty", name="")


def test_suffering_layer_basic() -> None:
    layer = SufferingLayer(
        id=slug_id("suffering", "disease burden"),
        name="disease burden",
        description="Global morbidity and mortality from treatable disease.",
    )
    assert layer.id == "suffering_disease-burden"
    assert layer.kind == "suffering_layer"


def test_suffering_layer_requires_name() -> None:
    with pytest.raises(ValidationError):
        SufferingLayer(id="suffering_empty", name="")


def test_intervention_scored_against_suffering() -> None:
    intervention = Intervention(
        id=new_id("intv"),
        text="Scale alignment research.",
        action_kind=InterventionKind.TECHNICAL,
        leverage_score=0.6,
        suffering_reduction_scores={
            "suffering_disease-burden": 0.4,
            "suffering_mental-health": 0.2,
        },
    )
    assert intervention.suffering_reduction_scores["suffering_disease-burden"] == 0.4


def test_intervention_suffering_scores_default_empty() -> None:
    intervention = Intervention(
        id=new_id("intv"),
        text="x",
        action_kind=InterventionKind.TECHNICAL,
        leverage_score=0.5,
    )
    assert intervention.suffering_reduction_scores == {}


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


def test_source_requires_title_and_reliability() -> None:
    source = Source(
        id=new_id("src"),
        source_kind=SourceKind.PAPER,
        title="Epoch AI compute trends 2024",
        url="https://epoch.ai/trends",
        authors=["Epoch AI staff"],
        published_at="2024",
        reliability=0.8,
    )
    assert source.source_kind is SourceKind.PAPER
    assert source.reliability == 0.8


def test_source_rejects_bad_reliability() -> None:
    with pytest.raises(ValidationError):
        Source(
            id=new_id("src"),
            source_kind=SourceKind.BLOG,
            title="x",
            reliability=1.5,
        )


def test_source_rejects_empty_title() -> None:
    with pytest.raises(ValidationError):
        Source(
            id=new_id("src"),
            source_kind=SourceKind.BLOG,
            title="",
            reliability=0.5,
        )


def test_warrant_basic() -> None:
    warrant = Warrant(
        id=new_id("war"),
        claim_id="desc_compute_matters",
        source_id="src_epoch",
        locator="figure 3",
        quote="Training compute grew 4x/year from 2018-2024.",
        method_tag=MethodTag.DIRECT_MEASUREMENT,
        supports=Support.SUPPORT,
        weight=0.9,
    )
    assert warrant.method_tag is MethodTag.DIRECT_MEASUREMENT
    assert warrant.supports is Support.SUPPORT


def test_warrant_defaults_to_support() -> None:
    warrant = Warrant(
        id=new_id("war"),
        claim_id="desc_x",
        source_id="src_x",
        method_tag=MethodTag.JOURNALISTIC_REPORT,
        weight=0.5,
    )
    assert warrant.supports is Support.SUPPORT


def test_warrant_contradict_allowed() -> None:
    warrant = Warrant(
        id=new_id("war"),
        claim_id="desc_x",
        source_id="src_x",
        method_tag=MethodTag.JOURNALISTIC_REPORT,
        supports=Support.CONTRADICT,
        weight=0.4,
    )
    assert warrant.supports is Support.CONTRADICT


def test_warrant_rejects_bad_weight() -> None:
    with pytest.raises(ValidationError):
        Warrant(
            id=new_id("war"),
            claim_id="desc_x",
            source_id="src_x",
            method_tag=MethodTag.EXPERT_ESTIMATE,
            weight=1.5,
        )


def test_camp_disputed_warrants_default_empty() -> None:
    camp = Camp(id="camp_test", name="Test")
    assert camp.disputed_warrants == []


def test_camp_disputed_warrants_accepts_refs() -> None:
    camp = Camp(
        id="camp_test",
        name="Test",
        held_descriptive=["desc_x"],
        disputed_warrants=["war_abc123"],
    )
    assert camp.disputed_warrants == ["war_abc123"]


@pytest.mark.parametrize(
    "model_factory",
    [
        lambda: DescriptiveClaim(id=new_id("desc"), text="x", confidence=0.5),
        lambda: NormativeClaim(id=new_id("norm"), text="x"),
        lambda: Camp(id=slug_id("camp", "Anthropic"), name="Anthropic"),
        lambda: Intervention(
            id=new_id("intv"),
            text="x",
            action_kind=InterventionKind.TECHNICAL,
            leverage_score=0.5,
        ),
        lambda: FrictionLayer(id=slug_id("friction", "capex"), name="capex"),
        lambda: HarmLayer(id=slug_id("harm", "water"), name="water"),
        lambda: SufferingLayer(
            id=slug_id("suffering", "poverty"), name="poverty"
        ),
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
        lambda: Source(
            id=new_id("src"),
            source_kind=SourceKind.FILING,
            title="Palantir 2024 10-K",
            reliability=0.85,
        ),
        lambda: Warrant(
            id=new_id("war"),
            claim_id="desc_x",
            source_id="src_x",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            weight=0.7,
        ),
    ],
)
def test_round_trip_through_dict(model_factory: object) -> None:
    """Every node must dict-serialize and rebuild identically --- required for YAML storage."""
    original = model_factory()  # type: ignore[operator]
    payload = original.model_dump(mode="json")
    rebuilt = type(original).model_validate(payload)
    assert rebuilt.model_dump(mode="json") == payload
