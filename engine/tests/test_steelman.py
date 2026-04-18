"""Steelman query: fixture-driven with a fake LLM client. No live API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from anthropic.types import TextBlock
from typer.testing import CliRunner

from afls.cli import app
from afls.output import (
    render_steelman_markdown,
    steelman_analysis_paths,
    write_steelman_json,
)
from afls.queries.palantir_seed import seed
from afls.queries.steelman import (
    SteelmanAnalysis,
    SteelmanFrame,
    SteelmanLLMOutput,
    build_steelman_context,
    compute_conceded_descriptive,
    run_steelman_query,
)
from afls.reasoning import AnthropicClient
from afls.schema import (
    BaseNode,
    Camp,
    DescriptiveClaim,
    Evidence,
    FrictionLayer,
    HarmLayer,
    Intervention,
    NormativeClaim,
    Source,
)
from afls.storage import list_nodes, save_node


@dataclass
class _FakeResponse:
    content: list[TextBlock]


class _FakeMessages:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        block = TextBlock(type="text", text=self._responses.pop(0), citations=None)
        return _FakeResponse(content=[block])


class _FakeSDK:
    def __init__(self, responses: list[str]) -> None:
        self.messages = _FakeMessages(responses)


def _client_with(responses: list[str]) -> AnthropicClient:
    sdk = _FakeSDK(responses)
    return AnthropicClient(sdk_client=cast(Any, sdk))


def _harm_layers() -> list[HarmLayer]:
    return [
        HarmLayer(id="harm_water", name="Water", description="Freshwater consumption."),
        HarmLayer(id="harm_extraction", name="Extraction", description="Mining harm."),
        HarmLayer(
            id="harm_concentration", name="Concentration", description="Gatekeeping."
        ),
    ]


def _extra_claim_and_camp() -> tuple[DescriptiveClaim, NormativeClaim, Camp]:
    desc = DescriptiveClaim(
        id="desc_water_harm",
        text="Compute buildout drains aquifers at siting scale.",
        confidence=0.8,
    )
    norm = NormativeClaim(
        id="norm_ecological_stewardship_test",
        text="Ecosystems have intrinsic standing.",
    )
    camp = Camp(
        id="camp_environmentalists_test",
        name="Environmentalists",
        summary="Conservation coalition.",
        held_descriptive=["desc_water_harm"],
        held_normative=["norm_ecological_stewardship_test"],
    )
    return desc, norm, camp


@pytest.fixture
def seeded_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    monkeypatch.setenv("AFLS_DATA_DIR", str(data))
    monkeypatch.setenv("AFLS_DB_PATH", str(tmp_path / "afls.db"))
    seed(data)

    extras: list[BaseNode] = list(_harm_layers())
    desc, norm, camp = _extra_claim_and_camp()
    extras.extend([desc, norm, camp])
    for node in extras:
        save_node(node, data)

    # Fold harm_scores onto the seed interventions so the steelman context has content.
    for intv in list_nodes(Intervention, data):
        if intv.id == "intv_compute":
            intv.harm_scores = {
                "harm_water": 0.2,
                "harm_extraction": 0.3,
                "harm_concentration": 0.2,
            }
            save_node(intv, data)
    return data


def _canned_llm_output() -> str:
    payload = {
        "case_for": [
            {
                "camp_id": "camp_anthropic",
                "normative_claim_ids": ["norm_anthropic_safety"],
                "descriptive_claim_ids": ["desc_compute_matters", "desc_water_harm"],
                "case": "Frontier compute is the limiting input on safe capability; "
                "accepting water cost buys leverage that offsets the harm.",
            },
            {
                "camp_id": "camp_environmentalists_test",
                "normative_claim_ids": ["norm_ecological_stewardship_test"],
                "descriptive_claim_ids": ["desc_compute_matters"],
                "case": "Stewardship includes the duty to steward human futures; "
                "failing to build may itself be a failure of care.",
            },
        ],
        "case_against": [
            {
                "camp_id": "camp_environmentalists_test",
                "normative_claim_ids": ["norm_ecological_stewardship_test"],
                "descriptive_claim_ids": ["desc_water_harm"],
                "case": "Aquifer depletion is a first-order wrong; no downstream "
                "benefit can offset what the intervention consumes.",
            },
            {
                "camp_id": "camp_operator",
                "normative_claim_ids": ["norm_operator_flourishing"],
                "descriptive_claim_ids": ["desc_water_harm"],
                "case": "Concentrated water harm in siting communities fails the "
                "distributional test even in operator-flourishing terms.",
            },
        ],
        "operator_tension": "The operator's e/acc-with-80K overlay reads compute "
        "expansion as load-bearing --- but the environmentalist case AGAINST attacks the "
        "frame the operator has not yet admitted carries weight.",
    }
    return json.dumps(payload)


def test_steelman_llm_output_schema_roundtrips() -> None:
    payload = json.loads(_canned_llm_output())
    parsed = SteelmanLLMOutput.model_validate(payload)
    assert len(parsed.case_for) == 2
    assert parsed.case_against[0].camp_id == "camp_environmentalists_test"
    assert parsed.operator_tension


def test_compute_conceded_descriptive_intersects_cited_evidence() -> None:
    case_for = [
        SteelmanFrame(
            camp_id="camp_anthropic",
            descriptive_claim_ids=["desc_a", "desc_b"],
            case="x",
        )
    ]
    case_against = [
        SteelmanFrame(
            camp_id="camp_environmentalists_test",
            descriptive_claim_ids=["desc_b", "desc_c"],
            case="x",
        )
    ]
    assert compute_conceded_descriptive(case_for, case_against) == ["desc_b"]


def test_compute_conceded_descriptive_empty_when_disjoint() -> None:
    case_for = [
        SteelmanFrame(
            camp_id="camp_anthropic",
            descriptive_claim_ids=["desc_a"],
            case="x",
        )
    ]
    case_against = [
        SteelmanFrame(
            camp_id="camp_environmentalists_test",
            descriptive_claim_ids=["desc_b"],
            case="x",
        )
    ]
    assert compute_conceded_descriptive(case_for, case_against) == []


def test_build_steelman_context_spotlights_target_and_harms(seeded_data: Path) -> None:
    target = next(
        i for i in list_nodes(Intervention, seeded_data) if i.id == "intv_compute"
    )
    camps = list_nodes(Camp, seeded_data)
    descriptives = list_nodes(DescriptiveClaim, seeded_data)
    normatives = list_nodes(NormativeClaim, seeded_data)
    interventions = list_nodes(Intervention, seeded_data)
    friction_layers = list_nodes(FrictionLayer, seeded_data)
    harm_layers = list_nodes(HarmLayer, seeded_data)
    evidence_list = list_nodes(Evidence, seeded_data)
    sources = list_nodes(Source, seeded_data)

    ctx = build_steelman_context(
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
    assert "# Target intervention (spotlight)" in ctx
    assert "intv_compute" in ctx
    assert "harm_water" in ctx
    assert "harm_scores" in ctx
    assert "camp_environmentalists_test" in ctx  # present camps list includes the fixture camp


def test_run_steelman_query_end_to_end(seeded_data: Path) -> None:
    client = _client_with([_canned_llm_output()])
    analysis = run_steelman_query(
        client, seeded_data, target_intervention_id="intv_compute"
    )

    assert analysis.target_intervention_id == "intv_compute"
    assert analysis.target_intervention_text.startswith("Expand frontier-lab compute")
    assert len(analysis.case_for) == 2
    assert len(analysis.case_against) == 2
    assert analysis.operator_tension
    # Conceded = intersection: desc_compute_matters and desc_water_harm are in for,
    # desc_water_harm is in against. So {desc_water_harm}.
    assert analysis.conceded_descriptive == ["desc_water_harm"]


def test_run_steelman_query_raises_when_target_missing(seeded_data: Path) -> None:
    client = _client_with(["{}"])
    with pytest.raises(RuntimeError, match="unknown intervention"):
        run_steelman_query(
            client, seeded_data, target_intervention_id="intv_does_not_exist"
        )


def test_steelman_analysis_round_trips_json(
    seeded_data: Path, tmp_path: Path
) -> None:
    client = _client_with([_canned_llm_output()])
    analysis = run_steelman_query(
        client, seeded_data, target_intervention_id="intv_compute"
    )
    json_path, _ = steelman_analysis_paths(tmp_path / "out", analysis)
    write_steelman_json(analysis, json_path)
    reloaded = SteelmanAnalysis.model_validate_json(json_path.read_text())
    assert reloaded.target_intervention_id == analysis.target_intervention_id
    assert reloaded.conceded_descriptive == analysis.conceded_descriptive
    assert len(reloaded.case_for) == len(analysis.case_for)


def test_render_steelman_markdown_includes_sections(seeded_data: Path) -> None:
    client = _client_with([_canned_llm_output()])
    analysis = run_steelman_query(
        client, seeded_data, target_intervention_id="intv_compute"
    )
    prose = render_steelman_markdown(analysis, seeded_data)
    assert "# Steelman analysis" in prose
    assert "## Operator tension" in prose
    assert "## Case FOR" in prose
    assert "## Case AGAINST" in prose
    assert "## Conceded descriptive ground" in prose
    assert "intv_compute" in prose


def test_query_cli_rejects_steelman_without_target(
    seeded_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = runner.invoke(app, ["query", "steelman"])
    assert result.exit_code == 1
    assert "requires --target" in result.output
