"""Ingest pipeline tests: stdlib fetcher + CLI end-to-end with mocked LLM + network."""

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
from afls.ingest.fetch import _truncate_utf8, extract_text
from afls.reasoning import AnthropicClient
from afls.schema import (
    DescriptiveClaim,
    Evidence,
    MethodTag,
    Source,
    SourceKind,
    Support,
)
from afls.storage import list_nodes, load_node, save_node

# --- fetch.py unit tests -------------------------------------------------


def test_extract_text_strips_script_and_style() -> None:
    html = (
        "<html><head><title>t</title><style>.x{}</style></head>"
        "<body><script>var x=1;</script><p>hello</p></body></html>"
    )
    text = extract_text(html)
    assert "hello" in text
    assert "var x=1" not in text
    assert ".x{}" not in text


def test_extract_text_strips_nav_footer_aside() -> None:
    html = (
        "<html><body>"
        "<nav>menu</nav><aside>ad</aside>"
        "<main><p>body content</p></main>"
        "<footer>© 2026</footer>"
        "</body></html>"
    )
    text = extract_text(html)
    assert "body content" in text
    assert "menu" not in text
    assert "ad" not in text
    assert "2026" not in text


def test_extract_text_preserves_ordering() -> None:
    html = "<p>one</p><p>two</p><p>three</p>"
    text = extract_text(html)
    lines = [line for line in text.splitlines() if line]
    assert lines == ["one", "two", "three"]


def test_truncate_utf8_respects_multibyte_boundary() -> None:
    text = "a" + "\u00e9" * 10
    truncated = _truncate_utf8(text, max_bytes=5)
    truncated.encode("utf-8")
    assert len(truncated.encode("utf-8")) <= 5


def test_truncate_utf8_noop_when_under_limit() -> None:
    assert _truncate_utf8("hello", max_bytes=100) == "hello"


# --- CLI end-to-end ------------------------------------------------------


@dataclass
class _FakeResponse:
    content: list[TextBlock]


class _FakeMessages:
    def __init__(self, payload: str) -> None:
        self._payload = payload
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        block = TextBlock(type="text", text=self._payload, citations=None)
        return _FakeResponse(content=[block])


class _FakeSDK:
    def __init__(self, payload: str) -> None:
        self.messages = _FakeMessages(payload)


def _fake_client(payload: str) -> AnthropicClient:
    sdk = _FakeSDK(payload)
    return AnthropicClient(sdk_client=cast(Any, sdk))


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "data"
    monkeypatch.setenv("AFLS_DATA_DIR", str(root))
    monkeypatch.setenv("AFLS_DB_PATH", str(tmp_path / "afls.db"))
    return root


def _install_fake_ingest(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fetched_text: str = "A 2026 study of frontier models.",
    final_url: str = "https://example.com/article",
    sha256: str = "deadbeef" * 8,
    llm_payload: dict[str, Any] | None = None,
) -> _FakeSDK:
    """Patch fetch + client so `afls ingest` makes no network calls."""
    monkeypatch.setattr(
        cli_module, "_fetch_for_ingest", lambda url: (final_url, fetched_text, sha256)
    )
    payload = json.dumps(
        llm_payload
        if llm_payload is not None
        else {
            "source": {
                "id_slug": "example_piece",
                "source_kind": "press",
                "title": "Example Piece",
                "authors": ["Jane Doe"],
                "published_at": "2026-04-18",
                "reliability": 0.5,
                "notes": "",
            },
            "claims": [
                {
                    "id_slug": "example_claim",
                    "text": "Something happened.",
                    "confidence": 0.6,
                },
            ],
            "evidence": [
                {
                    "claim_idx": 0,
                    "locator": "paragraph 3",
                    "quote": "Something happened.",
                    "method_tag": "journalistic_report",
                    "supports": "support",
                    "weight": 0.55,
                },
            ],
        }
    )
    sdk = _FakeSDK(payload)
    monkeypatch.setattr(
        cli_module,
        "_build_ingest_client",
        lambda: AnthropicClient(sdk_client=cast(Any, sdk)),
    )
    return sdk


def test_ingest_writes_source_claim_evidence(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ingest(monkeypatch)
    result = runner.invoke(app, ["ingest", "https://example.com/article"])
    assert result.exit_code == 0, result.output

    source = load_node(Source, "src_example_piece", data_root)
    assert source.title == "Example Piece"
    assert source.url == "https://example.com/article"
    assert source.authors == ["Jane Doe"]
    assert source.accessed_at  # auto-stamped
    assert source.provenance is not None
    assert source.provenance.method == "httpx"
    assert source.provenance.tool.startswith("afls-ingest/")
    assert source.provenance.raw_content_hash == "deadbeef" * 8
    assert source.provenance.git_sha

    claims = list_nodes(DescriptiveClaim, data_root)
    assert len(claims) == 1
    assert claims[0].id == "desc_example_claim"
    assert claims[0].text == "Something happened."
    assert claims[0].confidence == 0.6

    evidence = list_nodes(Evidence, data_root)
    assert len(evidence) == 1
    assert evidence[0].claim_id == "desc_example_claim"
    assert evidence[0].source_id == "src_example_piece"
    assert evidence[0].method_tag is MethodTag.JOURNALISTIC_REPORT
    assert evidence[0].supports is Support.SUPPORT
    assert evidence[0].weight == 0.55


def test_ingest_refuses_source_id_collision(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_node(
        Source(
            id="src_example_piece",
            source_kind=SourceKind.PRESS,
            title="already here",
            reliability=0.5,
        ),
        data_root,
    )
    _install_fake_ingest(monkeypatch)
    result = runner.invoke(app, ["ingest", "https://example.com/article"])
    assert result.exit_code == 1
    assert "collision" in result.output
    assert len(list_nodes(DescriptiveClaim, data_root)) == 0
    assert len(list_nodes(Evidence, data_root)) == 0


def test_ingest_refuses_claim_id_collision(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_node(
        DescriptiveClaim(id="desc_example_claim", text="x", confidence=0.2),
        data_root,
    )
    _install_fake_ingest(monkeypatch)
    result = runner.invoke(app, ["ingest", "https://example.com/article"])
    assert result.exit_code == 1
    assert "collision" in result.output
    assert len(list_nodes(Source, data_root)) == 0


def test_ingest_bails_on_empty_body(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ingest(monkeypatch, fetched_text="   \n  ")
    result = runner.invoke(app, ["ingest", "https://example.com/article"])
    assert result.exit_code == 1
    assert "no extractable text" in result.output


def test_ingest_bails_on_fetch_error(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(url: str) -> tuple[str, str, str]:
        raise RuntimeError("network gone")

    monkeypatch.setattr(cli_module, "_fetch_for_ingest", _boom)
    result = runner.invoke(app, ["ingest", "https://example.com/article"])
    assert result.exit_code == 1
    assert "fetch failed" in result.output
    assert "network gone" in result.output


def test_ingest_rejects_duplicate_llm_slugs(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "source": {
            "id_slug": "dup_test",
            "source_kind": "press",
            "title": "Dup",
            "authors": [],
            "published_at": "",
            "reliability": 0.5,
            "notes": "",
        },
        "claims": [
            {"id_slug": "same", "text": "first", "confidence": 0.5},
            {"id_slug": "same", "text": "second", "confidence": 0.5},
        ],
        "evidence": [
            {
                "claim_idx": 0,
                "locator": "",
                "quote": "",
                "method_tag": "journalistic_report",
                "supports": "support",
                "weight": 0.5,
            },
        ],
    }
    _install_fake_ingest(monkeypatch, llm_payload=payload)
    result = runner.invoke(app, ["ingest", "https://example.com/article"])
    assert result.exit_code == 1
    assert "duplicate claim id_slug" in result.output
    assert len(list_nodes(Source, data_root)) == 0


def test_ingest_rejects_out_of_range_claim_idx(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "source": {
            "id_slug": "oob_test",
            "source_kind": "press",
            "title": "OOB",
            "authors": [],
            "published_at": "",
            "reliability": 0.5,
            "notes": "",
        },
        "claims": [{"id_slug": "only_one", "text": "x", "confidence": 0.5}],
        "evidence": [
            {
                "claim_idx": 5,
                "locator": "",
                "quote": "",
                "method_tag": "journalistic_report",
                "supports": "support",
                "weight": 0.5,
            },
        ],
    }
    _install_fake_ingest(monkeypatch, llm_payload=payload)
    result = runner.invoke(app, ["ingest", "https://example.com/article"])
    assert result.exit_code == 1
    assert "claim_idx=5" in result.output
    assert len(list_nodes(Source, data_root)) == 0


def test_ingest_sha256_matches_text(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sha256 in provenance is whatever the fetcher returned; ingest doesn't re-hash."""
    _install_fake_ingest(monkeypatch, sha256="cafebabe" * 8)
    result = runner.invoke(app, ["ingest", "https://example.com/article"])
    assert result.exit_code == 0, result.output
    source = load_node(Source, "src_example_piece", data_root)
    assert source.provenance is not None
    assert source.provenance.raw_content_hash == "cafebabe" * 8
