"""Palantir query: seed + deterministic convergence + mocked-LLM run."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from anthropic.types import TextBlock
from typer.testing import CliRunner

from afls.cli import app
from afls.output import analysis_paths, render_analysis_markdown, write_analysis_json
from afls.queries.palantir import (
    PalantirAnalysis,
    PalantirLLMOutput,
    build_graph_context,
    find_contested_claims,
    find_descriptive_convergences,
    run_palantir_query,
)
from afls.queries.palantir_seed import seed
from afls.queries.research_seed import seed as seed_research
from afls.reasoning import AnthropicClient
from afls.schema import (
    Camp,
    DescriptiveClaim,
    Intervention,
    MethodTag,
    NormativeClaim,
    Source,
    SourceKind,
    Support,
    Warrant,
)
from afls.storage import list_nodes


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


@pytest.fixture
def seeded_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    monkeypatch.setenv("AFLS_DATA_DIR", str(data))
    monkeypatch.setenv("AFLS_DB_PATH", str(tmp_path / "afls.db"))
    count = seed(data)
    assert count > 0
    return data


def _canned_llm_output() -> str:
    payload = {
        "convergent_interventions": [
            {
                "intervention_id": "intv_compute",
                "supporting_camps": ["camp_palantir", "camp_anthropic", "camp_operator"],
                "divergent_reasons": {
                    "camp_palantir": "norm_palantir_national",
                    "camp_anthropic": "norm_anthropic_safety",
                    "camp_operator": "norm_operator_flourishing",
                },
                "operator_note": "Infrastructure as common ground; divergence is downstream.",
            },
            {
                "intervention_id": "intv_grid",
                "supporting_camps": ["camp_palantir", "camp_anthropic", "camp_operator"],
                "divergent_reasons": {
                    "camp_palantir": "norm_palantir_order",
                    "camp_anthropic": "norm_anthropic_safety",
                    "camp_operator": "norm_operator_sovereignty",
                },
                "operator_note": "",
            },
        ],
        "bridges": [
            {
                "from_camp": "camp_palantir",
                "to_camp": "camp_operator",
                "translation": "Robust infrastructure is a precondition for any deployment, "
                "whether pointed at dominance or flourishing.",
                "caveats": ["What the infrastructure gets pointed at does not translate."],
            },
            {
                "from_camp": "camp_anthropic",
                "to_camp": "camp_operator",
                "translation": "Alignment research reduces the chance of catastrophic "
                "outcomes that would foreclose flourishing.",
                "caveats": [],
            },
        ],
        "blindspots": [
            {
                "flagged_camp_id": "camp_palantir",
                "reasoning": "The operator under-weights the order-first framing even where "
                "it tracks legitimate concerns.",
            }
        ],
    }
    return json.dumps(payload)


def test_find_descriptive_convergences_intersects_held_descriptive() -> None:
    a = Camp(id="camp_a", name="A", held_descriptive=["x", "y", "z"])
    b = Camp(id="camp_b", name="B", held_descriptive=["y", "z"])
    c = Camp(id="camp_c", name="C", held_descriptive=["z", "y"])
    assert find_descriptive_convergences([a, b, c]) == ["y", "z"]


def test_find_descriptive_convergences_empty_when_no_camps() -> None:
    assert find_descriptive_convergences([]) == []


def test_find_descriptive_convergences_empty_when_disjoint() -> None:
    a = Camp(id="a", name="A", held_descriptive=["x"])
    b = Camp(id="b", name="B", held_descriptive=["y"])
    assert find_descriptive_convergences([a, b]) == []


def test_build_graph_context_includes_every_camp(seeded_data: Path) -> None:
    camps = list_nodes(Camp, seeded_data)
    descriptives = list_nodes(DescriptiveClaim, seeded_data)
    normatives = list_nodes(NormativeClaim, seeded_data)
    interventions = list_nodes(Intervention, seeded_data)
    ctx = build_graph_context(camps, descriptives, normatives, interventions)
    for camp in camps:
        assert camp.id in ctx
        assert camp.name in ctx
    for intv in interventions:
        assert intv.id in ctx


_SEED_CAMP_IDS = ("camp_palantir", "camp_anthropic", "camp_operator")


def test_run_palantir_query_end_to_end(seeded_data: Path) -> None:
    client = _client_with([_canned_llm_output()])
    analysis = run_palantir_query(client, seeded_data, camp_ids=_SEED_CAMP_IDS)

    assert analysis.camps == ["camp_palantir", "camp_anthropic", "camp_operator"]
    assert analysis.descriptive_convergences == [
        "desc_accelerating",
        "desc_compute_matters",
        "desc_grid_constraint",
    ]
    assert {c.intervention_id for c in analysis.convergent_interventions} == {
        "intv_compute",
        "intv_grid",
    }
    assert len(analysis.bridges) == 2
    assert all(b.id.startswith("bridge_") for b in analysis.bridges)
    assert all(b.against_prior_set == "BRAIN.md" for b in analysis.blindspots)
    assert len(analysis.blindspots) == 1


def test_run_palantir_query_raises_when_camp_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("AFLS_DATA_DIR", str(data))
    seed(data)
    (data / "camps" / "camp_palantir.yaml").unlink()
    client = _client_with(["{}"])
    with pytest.raises(RuntimeError, match="missing expected camps"):
        run_palantir_query(client, data)


def test_palantir_analysis_round_trips_json(seeded_data: Path, tmp_path: Path) -> None:
    client = _client_with([_canned_llm_output()])
    analysis = run_palantir_query(client, seeded_data, camp_ids=_SEED_CAMP_IDS)
    json_path, _ = analysis_paths(tmp_path / "out", analysis)
    write_analysis_json(analysis, json_path)
    reloaded = PalantirAnalysis.model_validate_json(json_path.read_text())
    assert reloaded.camps == analysis.camps
    assert reloaded.descriptive_convergences == analysis.descriptive_convergences
    assert len(reloaded.bridges) == len(analysis.bridges)


def test_render_markdown_includes_camp_names(seeded_data: Path) -> None:
    client = _client_with([_canned_llm_output()])
    analysis = run_palantir_query(client, seeded_data, camp_ids=_SEED_CAMP_IDS)
    prose = render_analysis_markdown(analysis, seeded_data)
    assert "Palantir" in prose
    assert "Anthropic" in prose
    assert "Operator-aligned" in prose
    assert "intv_compute" in prose
    assert "## Bridges" in prose
    assert "## Blindspots" in prose


def test_llm_output_schema_roundtrips() -> None:
    payload = json.loads(_canned_llm_output())
    parsed = PalantirLLMOutput.model_validate(payload)
    assert len(parsed.convergent_interventions) == 2
    assert parsed.bridges[0].from_camp == "camp_palantir"


def test_query_cli_rejects_unknown_name(
    seeded_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = runner.invoke(app, ["query", "bogus"])
    assert result.exit_code == 1
    assert "unknown query" in result.output


def test_query_cli_requires_api_key(
    seeded_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = runner.invoke(app, ["query", "palantir"])
    assert result.exit_code != 0


def _claim(id_: str) -> DescriptiveClaim:
    return DescriptiveClaim(id=id_, text=f"text for {id_}", confidence=0.8)


def _source(id_: str) -> Source:
    return Source(
        id=id_,
        source_kind=SourceKind.PAPER,
        title=f"Title {id_}",
        reliability=0.8,
    )


def _warrant(id_: str, claim_id: str, source_id: str, stance: Support) -> Warrant:
    return Warrant(
        id=id_,
        claim_id=claim_id,
        source_id=source_id,
        method_tag=MethodTag.DIRECT_MEASUREMENT,
        supports=stance,
        weight=0.8,
    )


def test_find_contested_claims_requires_support_and_contradict() -> None:
    claims = [_claim("desc_a"), _claim("desc_b"), _claim("desc_c")]
    sources = [_source("src_1"), _source("src_2")]
    warrants = [
        _warrant("war_a1", "desc_a", "src_1", Support.SUPPORT),
        _warrant("war_a2", "desc_a", "src_2", Support.CONTRADICT),
        _warrant("war_b1", "desc_b", "src_1", Support.SUPPORT),
        _warrant("war_c1", "desc_c", "src_1", Support.QUALIFY),
    ]
    contested = find_contested_claims(claims, warrants, sources)
    assert [c.claim_id for c in contested] == ["desc_a"]
    assert len(contested[0].supports) == 1
    assert len(contested[0].contradicts) == 1
    assert contested[0].supports[0].source_title == "Title src_1"


def test_find_contested_claims_includes_qualifies_on_contested_claim() -> None:
    claims = [_claim("desc_a")]
    sources = [_source("src_1"), _source("src_2"), _source("src_3")]
    warrants = [
        _warrant("war_a1", "desc_a", "src_1", Support.SUPPORT),
        _warrant("war_a2", "desc_a", "src_2", Support.CONTRADICT),
        _warrant("war_a3", "desc_a", "src_3", Support.QUALIFY),
    ]
    contested = find_contested_claims(claims, warrants, sources)
    assert len(contested) == 1
    assert len(contested[0].qualifies) == 1


def test_find_contested_claims_on_research_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The compute/grid research content includes a Goldman contradict on the
    datacenter load forecast. Verify we detect it."""
    data = tmp_path / "data"
    monkeypatch.setenv("AFLS_DATA_DIR", str(data))
    monkeypatch.setenv("AFLS_DB_PATH", str(tmp_path / "afls.db"))
    seed(data)
    seed_research(data)
    claims = list_nodes(DescriptiveClaim, data)
    warrants = list_nodes(Warrant, data)
    sources = list_nodes(Source, data)
    contested = find_contested_claims(claims, warrants, sources)
    ids = [c.claim_id for c in contested]
    assert "desc_us_datacenter_load_forecast" in ids
    claim = next(c for c in contested if c.claim_id == "desc_us_datacenter_load_forecast")
    assert any(w.source_id == "src_goldman_gen_power" for w in claim.contradicts)


def test_build_graph_context_includes_warrants_when_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("AFLS_DATA_DIR", str(data))
    monkeypatch.setenv("AFLS_DB_PATH", str(tmp_path / "afls.db"))
    seed(data)
    seed_research(data)
    camps = list_nodes(Camp, data)
    descriptives = list_nodes(DescriptiveClaim, data)
    normatives = list_nodes(NormativeClaim, data)
    interventions = list_nodes(Intervention, data)
    warrants = list_nodes(Warrant, data)
    sources = list_nodes(Source, data)
    ctx = build_graph_context(
        camps, descriptives, normatives, interventions, warrants, sources
    )
    assert "## Descriptive claims (with warrants)" in ctx
    assert "contradict" in ctx
    assert "src_goldman_gen_power" in ctx
