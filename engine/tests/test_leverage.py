"""Leverage query: deterministic ranking math + end-to-end with fake LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from anthropic.types import TextBlock
from pydantic import ValidationError

from afls.output import render_leverage_markdown
from afls.queries.leverage import (
    LeverageAnalysis,
    LeverageLLMOutput,
    LeverageRanking,
    build_leverage_context,
    rank_interventions,
    run_leverage_query,
)
from afls.queries.palantir_seed import seed
from afls.reasoning import AnthropicClient
from afls.schema import (
    Camp,
    DescriptiveClaim,
    HarmLayer,
    Intervention,
    InterventionKind,
    NormativeClaim,
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


def _intv(
    id_: str,
    *,
    leverage: float = 0.8,
    friction: dict[str, float] | None = None,
    harm: dict[str, float] | None = None,
    suffering: dict[str, float] | None = None,
) -> Intervention:
    return Intervention(
        id=id_,
        text=f"intervention {id_}",
        action_kind=InterventionKind.TECHNICAL,
        leverage_score=leverage,
        friction_scores=friction or {},
        harm_scores=harm or {},
        suffering_reduction_scores=suffering or {},
    )


def test_rank_interventions_computes_nested_composites() -> None:
    intv = _intv(
        "intv_a",
        leverage=0.5,
        friction={"friction_grid": 0.8, "friction_capex": 0.6},
        harm={"harm_water": 0.5, "harm_land": 0.3},
        suffering={"suffering_disease": 0.9, "suffering_mortality": 0.7},
    )
    rows = rank_interventions([intv])
    assert len(rows) == 1
    r = rows[0]
    assert r.mean_robustness == pytest.approx(0.7)
    assert r.mean_harm_robustness == pytest.approx(0.4)
    assert r.mean_suffering_reduction == pytest.approx(0.8)
    assert r.composite_score == pytest.approx(0.5 * 0.7)
    assert r.suffering_composite == pytest.approx(0.5 * 0.7 * 0.8)
    assert r.net_composite == pytest.approx(0.5 * 0.7 * 0.8 * 0.4)


def test_rank_interventions_zero_net_when_harm_scores_empty() -> None:
    """Absent harm_scores collapse net_composite to zero, same as absent suffering.

    This is intentional: no harm-scoring means the operator has not yet judged
    the intervention's harm profile, and the tool must not silently treat
    'unscored' as 'clean'.
    """
    intv = _intv(
        "intv_unscored_harm",
        leverage=0.9,
        friction={"friction_grid": 0.9},
        harm={},  # explicit empty --- not scored
        suffering={"suffering_disease": 0.9},
    )
    rows = rank_interventions([intv])
    assert rows[0].mean_harm_robustness == 0.0
    assert rows[0].net_composite == 0.0
    # But the pre-harm composite is still legible, so the operator can see the
    # ranking's shape before authoring harm scores.
    assert rows[0].suffering_composite == pytest.approx(0.9 * 0.9 * 0.9)


def test_rank_interventions_zero_net_when_suffering_scores_empty() -> None:
    """Mirror: absent suffering_reduction scores also collapse net to zero."""
    intv = _intv(
        "intv_no_suffering",
        leverage=0.9,
        friction={"friction_grid": 0.9},
        harm={"harm_water": 0.9},
        suffering={},
    )
    rows = rank_interventions([intv])
    assert rows[0].mean_suffering_reduction == 0.0
    assert rows[0].net_composite == 0.0
    assert rows[0].composite_score == pytest.approx(0.9 * 0.9)


def test_rank_interventions_sorts_by_net_composite_not_suffering_composite() -> None:
    """The load-bearing assertion: harm reorders the ranking.

    `clean` and `dirty` have identical friction/suffering scores; only their
    harm profile differs. Under the old suffering_composite sort they would
    tie and fall back to id; under net_composite `clean` must come first.
    """
    clean = _intv(
        "intv_clean",
        leverage=0.8,
        friction={"friction_grid": 0.9},
        harm={"harm_water": 0.9, "harm_land": 0.9},
        suffering={"suffering_disease": 0.8},
    )
    dirty = _intv(
        "intv_dirty",
        leverage=0.8,
        friction={"friction_grid": 0.9},
        harm={"harm_water": 0.2, "harm_land": 0.2},
        suffering={"suffering_disease": 0.8},
    )
    rows = rank_interventions([dirty, clean])  # input order: dirty first
    assert [r.intervention_id for r in rows] == ["intv_clean", "intv_dirty"]
    # And the old sort would have tied them:
    assert rows[0].suffering_composite == pytest.approx(rows[1].suffering_composite)


def test_rank_interventions_id_tiebreak_when_net_composite_equal() -> None:
    a = _intv(
        "intv_aaa",
        leverage=0.5,
        friction={"f": 0.5},
        harm={"h": 0.5},
        suffering={"s": 0.5},
    )
    b = _intv(
        "intv_bbb",
        leverage=0.5,
        friction={"f": 0.5},
        harm={"h": 0.5},
        suffering={"s": 0.5},
    )
    rows = rank_interventions([b, a])
    assert [r.intervention_id for r in rows] == ["intv_aaa", "intv_bbb"]


def test_ranking_exposes_harm_scores_for_downstream_rendering() -> None:
    """The site's RankingRow renders harm_scores as a bar; the schema must carry them."""
    intv = _intv(
        "intv_with_harm",
        leverage=0.7,
        friction={"friction_grid": 0.8},
        harm={"harm_water": 0.4, "harm_land": 0.6},
        suffering={"suffering_disease": 0.7},
    )
    rows = rank_interventions([intv])
    assert rows[0].harm_scores == {"harm_water": 0.4, "harm_land": 0.6}


def _canned_llm_output() -> str:
    payload = {
        "coalition_analyses": [
            {
                "intervention_id": "intv_compute",
                "supporting_camps": ["camp_palantir", "camp_anthropic"],
                "contesting_camps": ["camp_operator"],
                "expected_friction": "Grid capex binds first; water harm "
                "under-counted given siting reality.",
            }
        ],
        "ranking_blindspots": [
            {
                "flagged_intervention_id": "intv_grid",
                "reasoning": "Grid intervention has zero suffering numerator but "
                "enables every downstream reduction.",
            }
        ],
    }
    return json.dumps(payload)


@pytest.fixture
def seeded_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    monkeypatch.setenv("AFLS_DATA_DIR", str(data))
    monkeypatch.setenv("AFLS_DB_PATH", str(tmp_path / "afls.db"))
    seed(data)
    # Fold harm layers + harm_scores on intv_compute so the leverage prompt has
    # something to reason over. Mirrors the steelman fixture setup.
    for layer in (
        HarmLayer(id="harm_water", name="Water", description="Freshwater drain."),
        HarmLayer(id="harm_land", name="Land", description="Land use."),
    ):
        save_node(layer, data)
    for intv in list_nodes(Intervention, data):
        if intv.id == "intv_compute":
            intv.harm_scores = {"harm_water": 0.2, "harm_land": 0.5}
            save_node(intv, data)
    return data


_SEED_CAMP_IDS = ("camp_palantir", "camp_anthropic", "camp_operator")


def test_run_leverage_query_end_to_end(seeded_data: Path) -> None:
    client = _client_with([_canned_llm_output()])
    analysis = run_leverage_query(client, seeded_data, camp_ids=_SEED_CAMP_IDS)
    assert set(analysis.camps) == set(_SEED_CAMP_IDS)
    assert len(analysis.rankings) > 0
    # intv_compute now has harm_scores; confirm they flow through the ranking.
    compute_row = next(
        r for r in analysis.rankings if r.intervention_id == "intv_compute"
    )
    assert compute_row.harm_scores == {"harm_water": 0.2, "harm_land": 0.5}
    assert compute_row.mean_harm_robustness == pytest.approx(0.35)
    # And the deterministic sort is by net_composite.
    scores = [r.net_composite for r in analysis.rankings]
    assert scores == sorted(scores, reverse=True)


def test_build_leverage_context_includes_harm_semantic(seeded_data: Path) -> None:
    camps = [c for c in list_nodes(Camp, seeded_data) if c.id in _SEED_CAMP_IDS]
    descriptives = list_nodes(DescriptiveClaim, seeded_data)
    normatives = list_nodes(NormativeClaim, seeded_data)
    interventions = list_nodes(Intervention, seeded_data)
    rankings = rank_interventions(interventions)
    ctx = build_leverage_context(camps, rankings, descriptives, normatives)
    assert "Harm semantic" in ctx
    assert "net_composite" in ctx
    # intv_compute's harm scores render in the formatted row.
    assert "harm_water=0.2" in ctx


def test_leverage_analysis_roundtrip_preserves_harm(seeded_data: Path) -> None:
    """JSON round-trip must preserve mean_harm_robustness, harm_scores, net_composite."""
    client = _client_with([_canned_llm_output()])
    analysis = run_leverage_query(client, seeded_data, camp_ids=_SEED_CAMP_IDS)
    payload = analysis.model_dump_json()
    reloaded = LeverageAnalysis.model_validate_json(payload)
    compute_before = next(
        r for r in analysis.rankings if r.intervention_id == "intv_compute"
    )
    compute_after = next(
        r for r in reloaded.rankings if r.intervention_id == "intv_compute"
    )
    assert compute_after.mean_harm_robustness == compute_before.mean_harm_robustness
    assert compute_after.net_composite == compute_before.net_composite
    assert compute_after.harm_scores == compute_before.harm_scores


def test_leverage_llm_output_schema_roundtrips() -> None:
    payload = json.loads(_canned_llm_output())
    parsed = LeverageLLMOutput.model_validate(payload)
    assert len(parsed.coalition_analyses) == 1
    assert parsed.coalition_analyses[0].intervention_id == "intv_compute"


def test_render_leverage_markdown_surfaces_net_composite(seeded_data: Path) -> None:
    """The prose companion must call out the harm-netted composite, not just suffering_composite."""
    client = _client_with([_canned_llm_output()])
    analysis = run_leverage_query(client, seeded_data, camp_ids=_SEED_CAMP_IDS)
    prose = render_leverage_markdown(analysis, seeded_data)
    assert "net_composite" in prose
    assert "harm_robustness" in prose
    assert "net of harm" in prose


def test_ranking_is_sortable_with_zero_net_rows() -> None:
    """Interventions with empty harm or suffering (net=0) sort to the bottom.

    Regression guard: if `rank_interventions` ever tries to divide by the mean
    or otherwise special-case zero, it would break this case. Keep the sort
    pure.
    """
    scored = _intv(
        "intv_scored",
        leverage=0.8,
        friction={"f": 0.8},
        harm={"h": 0.8},
        suffering={"s": 0.8},
    )
    no_harm = _intv(
        "intv_no_harm",
        leverage=0.9,
        friction={"f": 0.9},
        harm={},
        suffering={"s": 0.9},
    )
    no_suffering = _intv(
        "intv_no_suffering",
        leverage=0.9,
        friction={"f": 0.9},
        harm={"h": 0.9},
        suffering={},
    )
    rows = rank_interventions([no_harm, no_suffering, scored])
    assert rows[0].intervention_id == "intv_scored"
    assert all(r.net_composite == 0.0 for r in rows[1:])


def test_ranking_row_model_rejects_unknown_fields() -> None:
    """extra='forbid' is load-bearing for the presentation boundary."""
    with pytest.raises(ValidationError):
        LeverageRanking.model_validate(
            {
                "intervention_id": "intv_x",
                "intervention_text": "x",
                "leverage_score": 0.5,
                "mean_robustness": 0.5,
                "mean_harm_robustness": 0.5,
                "mean_suffering_reduction": 0.5,
                "composite_score": 0.25,
                "suffering_composite": 0.125,
                "net_composite": 0.0625,
                "friction_scores": {},
                "harm_scores": {},
                "suffering_reduction_scores": {},
                "extra_field": "not allowed",
            }
        )
