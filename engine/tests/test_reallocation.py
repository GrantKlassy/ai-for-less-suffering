"""Reallocation query: pair-delta math + harm-divergence flagging + end-to-end."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from anthropic.types import TextBlock
from pydantic import ValidationError

from afls.output import (
    reallocation_analysis_paths,
    render_reallocation_markdown,
    write_reallocation_json,
    write_reallocation_markdown,
)
from afls.queries.leverage import LeverageRanking, rank_interventions
from afls.queries.palantir_seed import seed
from afls.queries.reallocation import (
    HARM_DIVERGENCE_THRESHOLD,
    ReallocationAnalysis,
    ReallocationLLMOutput,
    ReallocationPair,
    build_reallocation_context,
    compute_reallocation_pairs,
    run_reallocation_query,
)
from afls.reasoning import AnthropicClient
from afls.schema import HarmLayer, Intervention, InterventionKind
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


def _rank(intvs: list[Intervention]) -> list[LeverageRanking]:
    return rank_interventions(intvs)


def test_compute_pairs_returns_cartesian_minus_identity() -> None:
    """Every ordered pair except (x, x). N interventions → N*(N-1) candidate pairs."""
    intvs = [
        _intv("intv_a", friction={"f": 0.5}, harm={"h": 0.5}, suffering={"s": 0.5}),
        _intv("intv_b", friction={"f": 0.5}, harm={"h": 0.5}, suffering={"s": 0.5}),
        _intv("intv_c", friction={"f": 0.5}, harm={"h": 0.5}, suffering={"s": 0.5}),
    ]
    rankings = _rank(intvs)
    positive, flagged = compute_reallocation_pairs(rankings)
    # All tied on net_composite → delta_net == 0 for every pair → none positive.
    assert positive == []
    assert flagged == []


def test_compute_pairs_only_positive_delta_net_enter_main_list() -> None:
    """Non-positive delta_net moves are dropped, not negated and kept."""
    high = _intv(
        "intv_high",
        leverage=0.9,
        friction={"f": 0.9},
        harm={"h": 0.9},
        suffering={"s": 0.9},
    )
    low = _intv(
        "intv_low",
        leverage=0.3,
        friction={"f": 0.3},
        harm={"h": 0.3},
        suffering={"s": 0.3},
    )
    rankings = _rank([high, low])
    positive, _ = compute_reallocation_pairs(rankings)
    # Only (low -> high) has delta_net > 0. (high -> low) is dropped.
    assert len(positive) == 1
    assert positive[0].from_intervention_id == "intv_low"
    assert positive[0].to_intervention_id == "intv_high"
    assert positive[0].delta_net > 0


def test_compute_pairs_sorts_positive_by_delta_net_descending() -> None:
    """Larger gains sort ahead of smaller gains."""
    a = _intv(
        "intv_a",
        leverage=0.2,
        friction={"f": 0.2},
        harm={"h": 0.2},
        suffering={"s": 0.2},
    )
    b = _intv(
        "intv_b",
        leverage=0.5,
        friction={"f": 0.5},
        harm={"h": 0.5},
        suffering={"s": 0.5},
    )
    c = _intv(
        "intv_c",
        leverage=0.9,
        friction={"f": 0.9},
        harm={"h": 0.9},
        suffering={"s": 0.9},
    )
    rankings = _rank([a, b, c])
    positive, _ = compute_reallocation_pairs(rankings)
    # a→c is the biggest gain, then a→b and b→c (close), then others.
    deltas = [p.delta_net for p in positive]
    assert deltas == sorted(deltas, reverse=True)
    assert positive[0].from_intervention_id == "intv_a"
    assert positive[0].to_intervention_id == "intv_c"


def test_compute_pairs_harm_flag_fires_below_threshold() -> None:
    """A pair whose destination is materially dirtier than the source is flagged.

    Both interventions have the same suffering/friction/leverage; only harm
    differs. The destination has harm_robustness 0.2 vs. the source's 0.9 ---
    a drop of 0.7, well below -HARM_DIVERGENCE_THRESHOLD (-0.10).
    """
    clean = _intv(
        "intv_clean",
        leverage=0.5,
        friction={"f": 0.5},
        harm={"h": 0.9},
        suffering={"s": 0.5},
    )
    dirty = _intv(
        "intv_dirty",
        leverage=0.5,
        friction={"f": 0.5},
        harm={"h": 0.2},
        suffering={"s": 0.5},
    )
    rankings = _rank([clean, dirty])
    _, flagged = compute_reallocation_pairs(rankings)
    # Only (clean → dirty) should be flagged: that's the direction harm worsens.
    assert len(flagged) == 1
    assert flagged[0].from_intervention_id == "intv_clean"
    assert flagged[0].to_intervention_id == "intv_dirty"
    assert flagged[0].delta_harm_robustness < -HARM_DIVERGENCE_THRESHOLD


def test_compute_pairs_harm_flag_does_not_fire_within_threshold() -> None:
    """A tiny harm drop (below threshold magnitude) is not flagged."""
    a = _intv(
        "intv_a",
        leverage=0.5,
        friction={"f": 0.5},
        harm={"h": 0.55},  # delta 0.05 is inside -0.10 threshold
        suffering={"s": 0.5},
    )
    b = _intv(
        "intv_b",
        leverage=0.5,
        friction={"f": 0.5},
        harm={"h": 0.50},
        suffering={"s": 0.5},
    )
    rankings = _rank([a, b])
    _, flagged = compute_reallocation_pairs(rankings)
    assert flagged == []


def test_compute_pairs_flagged_sorted_worst_first() -> None:
    """Harm-flagged pairs sort by delta_harm_robustness ascending (worst first)."""
    clean = _intv(
        "intv_clean",
        leverage=0.5,
        friction={"f": 0.5},
        harm={"h": 0.9},
        suffering={"s": 0.5},
    )
    medium = _intv(
        "intv_medium",
        leverage=0.5,
        friction={"f": 0.5},
        harm={"h": 0.5},
        suffering={"s": 0.5},
    )
    dirty = _intv(
        "intv_dirty",
        leverage=0.5,
        friction={"f": 0.5},
        harm={"h": 0.1},
        suffering={"s": 0.5},
    )
    rankings = _rank([clean, medium, dirty])
    _, flagged = compute_reallocation_pairs(rankings)
    # Flagged pairs: clean→medium (-0.4), clean→dirty (-0.8), medium→dirty (-0.4).
    # Worst first: clean→dirty, then ties broken by id.
    assert flagged[0].from_intervention_id == "intv_clean"
    assert flagged[0].to_intervention_id == "intv_dirty"
    deltas = [p.delta_harm_robustness for p in flagged]
    assert deltas == sorted(deltas)


def test_compute_pairs_pair_in_both_lists_is_suffering_gain_harm_cost() -> None:
    """A pair can appear in both positive-pairs and harm-flagged. That's the
    key trade the operator needs to see --- gain suffering reduction at a
    material harm cost.
    """
    source = _intv(
        "intv_source",
        leverage=0.4,
        friction={"f": 0.4},
        harm={"h": 0.9},  # very clean
        suffering={"s": 0.3},  # low suffering gain
    )
    dest = _intv(
        "intv_dest",
        leverage=0.9,
        friction={"f": 0.9},
        harm={"h": 0.3},  # dirtier
        suffering={"s": 0.9},  # much higher suffering gain
    )
    rankings = _rank([source, dest])
    positive, flagged = compute_reallocation_pairs(rankings)
    # source → dest has positive net (suffering gain dominates) AND harm flag.
    assert any(
        p.from_intervention_id == "intv_source"
        and p.to_intervention_id == "intv_dest"
        for p in positive
    )
    assert any(
        p.from_intervention_id == "intv_source"
        and p.to_intervention_id == "intv_dest"
        for p in flagged
    )


def test_compute_pairs_empty_rankings_returns_empty() -> None:
    positive, flagged = compute_reallocation_pairs([])
    assert positive == []
    assert flagged == []


def test_compute_pairs_single_ranking_returns_empty() -> None:
    """A single intervention can't reallocate to anything."""
    intv = _intv(
        "intv_solo",
        friction={"f": 0.5},
        harm={"h": 0.5},
        suffering={"s": 0.5},
    )
    rankings = _rank([intv])
    positive, flagged = compute_reallocation_pairs(rankings)
    assert positive == []
    assert flagged == []


def test_reallocation_pair_per_term_deltas_match_source_to_dest_diff() -> None:
    """delta_suffering_composite, delta_harm_robustness, delta_viability must
    decompose cleanly from the endpoint ranking rows.
    """
    source = _intv(
        "intv_source",
        leverage=0.5,
        friction={"f": 0.5},
        harm={"h": 0.3},
        suffering={"s": 0.3},
    )
    dest = _intv(
        "intv_dest",
        leverage=0.8,
        friction={"f": 0.8},
        harm={"h": 0.7},
        suffering={"s": 0.7},
    )
    rankings = _rank([source, dest])
    by_id = {r.intervention_id: r for r in rankings}
    s, d = by_id["intv_source"], by_id["intv_dest"]
    positive, _ = compute_reallocation_pairs(rankings)
    pair = next(
        p for p in positive
        if p.from_intervention_id == "intv_source"
        and p.to_intervention_id == "intv_dest"
    )
    assert pair.delta_net == pytest.approx(d.net_composite - s.net_composite)
    assert pair.delta_suffering_composite == pytest.approx(
        d.suffering_composite - s.suffering_composite
    )
    assert pair.delta_harm_robustness == pytest.approx(
        d.mean_harm_robustness - s.mean_harm_robustness
    )
    assert pair.delta_viability == pytest.approx(
        d.composite_score - s.composite_score
    )


def _canned_llm_output() -> str:
    payload = {
        "coalition_shifts": [
            {
                "from_intervention_id": "intv_grid",
                "to_intervention_id": "intv_compute",
                "gaining_camps": ["camp_palantir"],
                "losing_camps": ["camp_operator"],
                "friction_rebinds": "Moving from grid-scale work to compute-"
                "scale work re-binds friction to capex and water; water harm "
                "is real, not a scoring artifact.",
            }
        ],
        "reallocation_blindspots": [
            {
                "flagged_from_intervention_id": "intv_grid",
                "flagged_to_intervention_id": "intv_compute",
                "reasoning": "intv_grid is enabling infrastructure; pulling "
                "effort from it would collapse intv_compute's friction "
                "robustness.",
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
    for layer in (
        HarmLayer(id="harm_water", name="Water", description="Freshwater drain."),
        HarmLayer(id="harm_land", name="Land", description="Land use."),
    ):
        save_node(layer, data)
    # Give one intervention a dirty harm profile so the sort + flag lists have
    # something to exercise end-to-end.
    for intv in list_nodes(Intervention, data):
        if intv.id == "intv_compute":
            intv.harm_scores = {"harm_water": 0.2, "harm_land": 0.4}
            save_node(intv, data)
        elif intv.id == "intv_grid":
            intv.harm_scores = {"harm_water": 0.9, "harm_land": 0.9}
            save_node(intv, data)
    return data


_SEED_CAMP_IDS = ("camp_palantir", "camp_anthropic", "camp_operator")


def test_run_reallocation_query_end_to_end(seeded_data: Path) -> None:
    client = _client_with([_canned_llm_output()])
    analysis = run_reallocation_query(
        client, seeded_data, camp_ids=_SEED_CAMP_IDS
    )
    assert set(analysis.camps) == set(_SEED_CAMP_IDS)
    assert len(analysis.rankings) > 0
    # Deterministic pair sort must hold for whatever the seed produced.
    assert all(p.delta_net > 0 for p in analysis.pairs)
    deltas = [p.delta_net for p in analysis.pairs]
    assert deltas == sorted(deltas, reverse=True)
    # LLM output surfaces unchanged.
    assert len(analysis.coalition_shifts) == 1
    assert analysis.coalition_shifts[0].from_intervention_id == "intv_grid"
    assert len(analysis.reallocation_blindspots) == 1


def test_build_reallocation_context_includes_pair_and_camp_sections(
    seeded_data: Path,
) -> None:
    from afls.schema import Camp, DescriptiveClaim, NormativeClaim

    camps = [c for c in list_nodes(Camp, seeded_data) if c.id in _SEED_CAMP_IDS]
    camps.sort(key=lambda c: _SEED_CAMP_IDS.index(c.id))
    descriptives = list_nodes(DescriptiveClaim, seeded_data)
    normatives = list_nodes(NormativeClaim, seeded_data)
    interventions = list_nodes(Intervention, seeded_data)
    rankings = rank_interventions(interventions)
    positive, flagged = compute_reallocation_pairs(rankings)
    ctx = build_reallocation_context(
        camps, rankings, positive[:5], flagged, descriptives, normatives
    )
    assert "reallocation pair" in ctx.lower()
    assert "net_composite" in ctx
    assert "harm_divergence_flags" in ctx or "Harm-divergence" in ctx
    # Camp section is rendered with ids the LLM will cite.
    assert "camp_palantir" in ctx


def test_reallocation_analysis_roundtrips_through_json(seeded_data: Path) -> None:
    client = _client_with([_canned_llm_output()])
    analysis = run_reallocation_query(
        client, seeded_data, camp_ids=_SEED_CAMP_IDS
    )
    payload = analysis.model_dump_json()
    reloaded = ReallocationAnalysis.model_validate_json(payload)
    assert [p.delta_net for p in reloaded.pairs] == [
        p.delta_net for p in analysis.pairs
    ]
    assert len(reloaded.coalition_shifts) == len(analysis.coalition_shifts)
    assert len(reloaded.reallocation_blindspots) == len(
        analysis.reallocation_blindspots
    )


def test_reallocation_llm_output_schema_roundtrips() -> None:
    payload = json.loads(_canned_llm_output())
    parsed = ReallocationLLMOutput.model_validate(payload)
    assert len(parsed.coalition_shifts) == 1
    assert parsed.coalition_shifts[0].gaining_camps == ["camp_palantir"]


def test_reallocation_pair_model_rejects_unknown_fields() -> None:
    """extra='forbid' holds on the pair schema so the JSON boundary stays clean."""
    with pytest.raises(ValidationError):
        ReallocationPair.model_validate(
            {
                "from_intervention_id": "intv_a",
                "to_intervention_id": "intv_b",
                "from_net_composite": 0.1,
                "to_net_composite": 0.2,
                "delta_net": 0.1,
                "delta_suffering_composite": 0.1,
                "delta_harm_robustness": 0.0,
                "delta_viability": 0.0,
                "extra_field": "not allowed",
            }
        )


def test_render_reallocation_markdown_surfaces_key_sections(
    seeded_data: Path,
) -> None:
    client = _client_with([_canned_llm_output()])
    analysis = run_reallocation_query(
        client, seeded_data, camp_ids=_SEED_CAMP_IDS
    )
    prose = render_reallocation_markdown(analysis, seeded_data)
    assert "Reallocation analysis" in prose
    assert "delta_net" in prose
    assert "harm" in prose.lower()
    assert "Coalition shifts" in prose or "coalition" in prose.lower()


def test_write_reallocation_artifacts_round_trip(
    seeded_data: Path, tmp_path: Path
) -> None:
    """JSON + markdown both land on disk with the expected path shape."""
    client = _client_with([_canned_llm_output()])
    analysis = run_reallocation_query(
        client, seeded_data, camp_ids=_SEED_CAMP_IDS
    )
    public_output = tmp_path / "public-output"
    json_path, md_path = reallocation_analysis_paths(public_output, analysis)
    write_reallocation_json(analysis, json_path)
    write_reallocation_markdown(analysis, md_path, seeded_data)
    assert json_path.exists()
    assert md_path.exists()
    assert json_path.name.startswith("reallocation_")
    assert json_path.suffix == ".json"
    assert md_path.suffix == ".md"
    reloaded = ReallocationAnalysis.model_validate_json(json_path.read_text())
    assert reloaded.kind == "reallocation_analysis"
