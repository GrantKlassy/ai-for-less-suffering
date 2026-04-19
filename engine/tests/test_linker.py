"""Linker pipeline tests: Haiku pass mapping new claims to camps + CLI mutation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from anthropic.types import TextBlock
from typer.testing import CliRunner

from afls import cli as cli_module
from afls.cli import app
from afls.reasoning import AnthropicClient
from afls.reasoning.linker import (
    LinkerDraft,
    apply_linker_draft,
    run_linker_query,
    validate_linker_draft,
)
from afls.schema import Camp, DescriptiveClaim
from afls.storage import load_node, save_node


@dataclass
class _FakeResponse:
    content: list[TextBlock]


class _QueueMessages:
    """Fake SDK .messages returning queued payloads in order."""

    def __init__(self, payloads: list[str]) -> None:
        self._payloads = list(payloads)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if not self._payloads:
            raise RuntimeError("fake SDK exhausted payload queue")
        payload = self._payloads.pop(0)
        return _FakeResponse(
            content=[TextBlock(type="text", text=payload, citations=None)]
        )


class _QueueSDK:
    def __init__(self, payloads: list[str]) -> None:
        self.messages = _QueueMessages(payloads)


def _queue_client(payloads: list[str]) -> AnthropicClient:
    sdk = _QueueSDK(payloads)
    return AnthropicClient(sdk_client=cast(Any, sdk))


def _seed_two_camps(data_dir: Path) -> tuple[Camp, Camp]:
    camp_a = Camp(
        id="camp_a",
        name="Camp A",
        summary="Hypothetical camp A for linker tests.",
        agents=["agent_a"],
    )
    camp_b = Camp(
        id="camp_b",
        name="Camp B",
        summary="Hypothetical camp B for linker tests.",
        agents=["agent_b"],
    )
    save_node(camp_a, data_dir)
    save_node(camp_b, data_dir)
    return camp_a, camp_b


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "data"
    monkeypatch.setenv("AFLS_DATA_DIR", str(root))
    monkeypatch.setenv("AFLS_DB_PATH", str(tmp_path / "afls.db"))
    return root


def test_validate_linker_draft_rejects_unknown_camp_id() -> None:
    """A draft naming a camp id not in the loaded set raises ValueError."""
    draft = LinkerDraft(linkages={"desc_x": ["camp_phantom"]})
    with pytest.raises(ValueError, match="unknown camp ids"):
        validate_linker_draft(
            draft,
            valid_camp_ids={"camp_a", "camp_b"},
            valid_claim_ids={"desc_x"},
        )


def test_validate_linker_draft_rejects_unknown_claim_id() -> None:
    """A draft naming a claim id that wasn't in `new_claims` raises."""
    draft = LinkerDraft(linkages={"desc_invented": ["camp_a"]})
    with pytest.raises(ValueError, match="unknown claim ids"):
        validate_linker_draft(
            draft,
            valid_camp_ids={"camp_a"},
            valid_claim_ids={"desc_real"},
        )


def test_run_linker_query_rejects_hallucinated_camp(data_root: Path) -> None:
    """Full path: LLM returns a draft referencing a non-existent camp; query raises."""
    _seed_two_camps(data_root)
    claim = DescriptiveClaim(id="desc_new", text="A new claim.", confidence=0.7)
    save_node(claim, data_root)

    payload = json.dumps({"linkages": {"desc_new": ["camp_phantom"]}})
    client = _queue_client([payload])

    with pytest.raises(ValueError, match="unknown camp ids"):
        run_linker_query(client, data_root, new_claims=[claim])


def test_run_linker_query_no_claims_returns_empty_draft(data_root: Path) -> None:
    """Edge case: empty new_claims skips the LLM entirely."""
    _seed_two_camps(data_root)
    client = _queue_client([])
    draft = run_linker_query(client, data_root, new_claims=[])
    assert draft.linkages == {}


def test_apply_linker_draft_empty_linkage_is_no_op(data_root: Path) -> None:
    """A claim with `[]` touches no camp and counts as floating."""
    camp_a, _ = _seed_two_camps(data_root)
    draft = LinkerDraft(linkages={"desc_lonely": []})
    counts = apply_linker_draft(draft, data_root)
    assert counts == {"linked": 0, "floating": 1, "camps_touched": 0}
    reloaded = load_node(Camp, camp_a.id, data_root)
    assert reloaded.held_descriptive == []


def test_apply_linker_draft_mutation_is_idempotent(data_root: Path) -> None:
    """Re-applying the same draft does not duplicate claim ids in held_descriptive."""
    camp_a, camp_b = _seed_two_camps(data_root)
    draft = LinkerDraft(
        linkages={"desc_shared": [camp_a.id, camp_b.id]}
    )

    first = apply_linker_draft(draft, data_root)
    assert first["linked"] == 1
    assert first["camps_touched"] == 2
    reloaded_a = load_node(Camp, camp_a.id, data_root)
    reloaded_b = load_node(Camp, camp_b.id, data_root)
    assert reloaded_a.held_descriptive == ["desc_shared"]
    assert reloaded_b.held_descriptive == ["desc_shared"]

    second = apply_linker_draft(draft, data_root)
    assert second == {"linked": 1, "floating": 0, "camps_touched": 0}
    assert load_node(Camp, camp_a.id, data_root).held_descriptive == ["desc_shared"]
    assert load_node(Camp, camp_b.id, data_root).held_descriptive == ["desc_shared"]


def test_apply_linker_draft_preserves_existing_held_descriptive(data_root: Path) -> None:
    """Linking a new claim does not remove claims the camp already holds."""
    camp_a = Camp(
        id="camp_a",
        name="Camp A",
        summary="Has prior claims.",
        agents=["agent_a"],
        held_descriptive=["desc_existing"],
    )
    save_node(camp_a, data_root)
    draft = LinkerDraft(linkages={"desc_new": [camp_a.id]})
    apply_linker_draft(draft, data_root)
    reloaded = load_node(Camp, camp_a.id, data_root)
    assert reloaded.held_descriptive == ["desc_existing", "desc_new"]


# --- CLI end-to-end ------------------------------------------------------


def _ingest_payload(claim_slug: str = "linker_claim") -> str:
    return json.dumps({
        "source": {
            "id_slug": "linker_src",
            "source_kind": "press",
            "title": "Linker Source",
            "authors": [],
            "published_at": "2026-04-18",
            "reliability": 0.5,
            "notes": "",
        },
        "claims": [
            {
                "id_slug": claim_slug,
                "text": "A claim about something the camps could hold.",
                "confidence": 0.7,
            }
        ],
        "evidence": [
            {
                "claim_idx": 0,
                "locator": "p1",
                "quote": "",
                "method_tag": "journalistic_report",
                "supports": "support",
                "weight": 0.5,
            }
        ],
    })


def _linker_payload(claim_id: str, camp_ids: list[str]) -> str:
    return json.dumps({"linkages": {claim_id: camp_ids}})


def test_ingest_end_to_end_links_claims(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full ingest + linker: target camps are mutated on disk."""
    camp_a, camp_b = _seed_two_camps(data_root)

    monkeypatch.setattr(
        cli_module,
        "_fetch_for_ingest",
        lambda url: ("https://example.com/", "Article body.", "deadbeef" * 8),
    )
    payloads = [
        _ingest_payload(),
        _linker_payload("desc_linker_claim", [camp_a.id, camp_b.id]),
    ]
    sdk = _QueueSDK(payloads)
    monkeypatch.setattr(
        cli_module,
        "_build_ingest_client",
        lambda: AnthropicClient(sdk_client=cast(Any, sdk)),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["ingest", "https://example.com/"])
    assert result.exit_code == 0, result.output
    assert "linked: 1 claims" in result.output

    reloaded_a = load_node(Camp, camp_a.id, data_root)
    reloaded_b = load_node(Camp, camp_b.id, data_root)
    assert "desc_linker_claim" in reloaded_a.held_descriptive
    assert "desc_linker_claim" in reloaded_b.held_descriptive


def test_ingest_end_to_end_empty_linkage_floats_claim(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the linker returns `[]`, the claim is saved but no camp is mutated."""
    camp_a, camp_b = _seed_two_camps(data_root)

    monkeypatch.setattr(
        cli_module,
        "_fetch_for_ingest",
        lambda url: ("https://example.com/", "Article body.", "deadbeef" * 8),
    )
    payloads = [
        _ingest_payload(),
        _linker_payload("desc_linker_claim", []),
    ]
    sdk = _QueueSDK(payloads)
    monkeypatch.setattr(
        cli_module,
        "_build_ingest_client",
        lambda: AnthropicClient(sdk_client=cast(Any, sdk)),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["ingest", "https://example.com/"])
    assert result.exit_code == 0, result.output
    assert "(1 floating)" in result.output

    assert load_node(Camp, camp_a.id, data_root).held_descriptive == []
    assert load_node(Camp, camp_b.id, data_root).held_descriptive == []
