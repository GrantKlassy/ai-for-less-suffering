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
from afls.ingest.fetch import count_paragraph_tags, extract_text, truncate_utf8
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


def testtruncate_utf8_respects_multibyte_boundary() -> None:
    text = "a" + "\u00e9" * 10
    truncated = truncate_utf8(text, max_bytes=5)
    truncated.encode("utf-8")
    assert len(truncated.encode("utf-8")) <= 5


def testtruncate_utf8_noop_when_under_limit() -> None:
    assert truncate_utf8("hello", max_bytes=100) == "hello"


def testcount_paragraph_tags_matches_bare_and_attributed() -> None:
    html = '<p>a</p><p class="b">b</p><p data-x="c">c</p>'
    assert count_paragraph_tags(html) == 3


def testcount_paragraph_tags_ignores_sibling_p_prefixed_tags() -> None:
    """`<pre>`, `<picture>`, `<path>` all start with `<p` but are not paragraphs."""
    html = "<pre>code</pre><picture></picture><path></path>"
    assert count_paragraph_tags(html) == 0


def testcount_paragraph_tags_returns_zero_on_empty() -> None:
    assert count_paragraph_tags("") == 0


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
    paragraph_count: int = 10,
    llm_payload: dict[str, Any] | None = None,
) -> _FakeSDK:
    """Patch fetch + client so `afls ingest` makes no network calls."""
    monkeypatch.setattr(
        cli_module,
        "_fetch_for_ingest",
        lambda url: (final_url, fetched_text, sha256, paragraph_count),
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
    result = runner.invoke(app, ["ingest:url", "https://example.com/article"])
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
    result = runner.invoke(app, ["ingest:url", "https://example.com/article"])
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
    result = runner.invoke(app, ["ingest:url", "https://example.com/article"])
    assert result.exit_code == 1
    assert "collision" in result.output
    assert len(list_nodes(Source, data_root)) == 0


def test_ingest_bails_on_empty_body(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ingest(monkeypatch, fetched_text="   \n  ")
    result = runner.invoke(app, ["ingest:url", "https://example.com/article"])
    assert result.exit_code == 1
    assert "no extractable text" in result.output


def test_ingest_bails_on_fetch_error(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(url: str) -> tuple[str, str, str, int]:
        raise RuntimeError("network gone")

    monkeypatch.setattr(cli_module, "_fetch_for_ingest", _boom)
    result = runner.invoke(app, ["ingest:url", "https://example.com/article"])
    assert result.exit_code == 1
    assert "fetch failed" in result.output
    assert "network gone" in result.output


def test_ingest_bails_when_paragraph_count_below_floor(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Precheck fires before the LLM call when raw HTML has too few `<p>` tags."""
    sdk = _install_fake_ingest(monkeypatch, paragraph_count=2)
    result = runner.invoke(app, ["ingest:url", "https://example.com/article"])
    assert result.exit_code == 1
    assert "precheck failed" in result.output
    assert "2 <p> tag" in result.output
    assert len(sdk.messages.calls) == 0
    assert len(list_nodes(Source, data_root)) == 0
    assert len(list_nodes(DescriptiveClaim, data_root)) == 0
    assert len(list_nodes(Evidence, data_root)) == 0


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
    result = runner.invoke(app, ["ingest:url", "https://example.com/article"])
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
    result = runner.invoke(app, ["ingest:url", "https://example.com/article"])
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
    result = runner.invoke(app, ["ingest:url", "https://example.com/article"])
    assert result.exit_code == 0, result.output
    source = load_node(Source, "src_example_piece", data_root)
    assert source.provenance is not None
    assert source.provenance.raw_content_hash == "cafebabe" * 8


def test_ingest_bare_alias_forwards_to_ingest_url(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bare `ingest` is hidden but still forwards to `ingest:url` for muscle memory."""
    _install_fake_ingest(monkeypatch)
    result = runner.invoke(app, ["ingest", "https://example.com/article"])
    assert result.exit_code == 0, result.output
    assert "renamed to `ingest:url`" in result.output
    assert load_node(Source, "src_example_piece", data_root).title == "Example Piece"


# --- read.py unit tests --------------------------------------------------


def _write_html_article(path: Path, body_tag: str = "article") -> None:
    """Write a minimal article HTML with enough <p> tags to pass precheck."""
    paragraphs = "".join(
        f"<p>Paragraph {i} of the {body_tag} content, with enough words to be real.</p>"
        for i in range(10)
    )
    path.write_text(
        f"<html><body>{paragraphs}</body></html>", encoding="utf-8"
    )


def test_read_and_extract_html_counts_paragraphs_and_builds_canonical_id(
    tmp_path: Path,
) -> None:
    from afls.ingest.read import read_and_extract

    article = tmp_path / "sub" / "article.html"
    article.parent.mkdir()
    _write_html_article(article)
    result = read_and_extract(article, root=tmp_path)
    assert result.kind == "html"
    assert result.paragraph_count == 10
    assert result.canonical_id == "file://sub/article.html"
    assert "Paragraph 0" in result.text
    assert result.sha256  # non-empty


def test_read_and_extract_markdown_has_zero_paragraph_count(tmp_path: Path) -> None:
    from afls.ingest.read import read_and_extract

    notes = tmp_path / "notes.md"
    notes.write_text("# Notes\n\nSome body text.", encoding="utf-8")
    result = read_and_extract(notes, root=tmp_path)
    assert result.kind == "text"
    assert result.paragraph_count == 0
    assert "Some body text" in result.text


def test_read_and_extract_pdf_dispatches_to_pdf_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """We don't generate a real PDF in tests --- just verify suffix dispatch routes
    through the PDF extractor, and that kind='pdf' + paragraph_count=0."""
    from afls.ingest import read as read_module

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"not a real pdf")
    monkeypatch.setattr(
        read_module, "_extract_pdf_text", lambda p: "fake pdf body text " * 30
    )
    result = read_module.read_and_extract(pdf_path, root=tmp_path)
    assert result.kind == "pdf"
    assert result.paragraph_count == 0
    assert "fake pdf body text" in result.text


def test_read_and_extract_rejects_unsupported_suffix(tmp_path: Path) -> None:
    from afls.ingest.read import UnsupportedFileType, read_and_extract

    binary = tmp_path / "mystery.bin"
    binary.write_bytes(b"\x00\x01\x02")
    with pytest.raises(UnsupportedFileType):
        read_and_extract(binary, root=tmp_path)


# --- ingest:dir CLI end-to-end ------------------------------------------


def _make_ingest_payload(source_slug: str, claim_slug: str) -> str:
    return json.dumps(
        {
            "source": {
                "id_slug": source_slug,
                "source_kind": "press",
                "title": f"Title {source_slug}",
                "authors": [],
                "published_at": "",
                "reliability": 0.5,
                "notes": "",
            },
            "claims": [
                {"id_slug": claim_slug, "text": "Something claimed.", "confidence": 0.5},
            ],
            "evidence": [
                {
                    "claim_idx": 0,
                    "locator": "paragraph 1",
                    "quote": "Something claimed.",
                    "method_tag": "journalistic_report",
                    "supports": "support",
                    "weight": 0.5,
                },
            ],
        }
    )


_LINKER_PAYLOAD: str = json.dumps({"linkages": {}})


class _FakeMessagesSequence:
    """Returns a different payload per call, in order. Last payload is repeated
    if the engine makes more calls than we staged (safety net, not a feature)."""

    def __init__(self, payloads: list[str]) -> None:
        self._payloads = payloads
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        idx = len(self.calls)
        self.calls.append(kwargs)
        payload = (
            self._payloads[idx] if idx < len(self._payloads) else self._payloads[-1]
        )
        block = TextBlock(type="text", text=payload, citations=None)
        return _FakeResponse(content=[block])


class _FakeSequenceSDK:
    def __init__(self, payloads: list[str]) -> None:
        self.messages = _FakeMessagesSequence(payloads)


def _install_fake_sequence(
    monkeypatch: pytest.MonkeyPatch, payloads: list[str]
) -> _FakeSequenceSDK:
    sdk = _FakeSequenceSDK(payloads)
    monkeypatch.setattr(
        cli_module,
        "_build_ingest_client",
        lambda: AnthropicClient(sdk_client=cast(Any, sdk)),
    )
    return sdk


def test_ingest_dir_walks_supported_files_and_links_once(
    runner: CliRunner,
    data_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved = tmp_path / "saved"
    saved.mkdir()
    _write_html_article(saved / "one.html")
    (saved / "notes.md").write_text(
        "# Notes\n\n" + ("Some body text. " * 40), encoding="utf-8"
    )

    payloads = [
        _make_ingest_payload("html_one", "claim_html_one"),
        _make_ingest_payload("md_notes", "claim_md_notes"),
        _LINKER_PAYLOAD,
    ]
    sdk = _install_fake_sequence(monkeypatch, payloads)

    result = runner.invoke(app, ["ingest:dir", str(saved)])
    assert result.exit_code == 0, result.output

    sources = list_nodes(Source, data_root)
    assert {s.id for s in sources} == {"src_html_one", "src_md_notes"}

    for s in sources:
        assert s.url.startswith("file://")
        assert s.provenance is not None
        assert s.provenance.method == "file"
        assert s.provenance.raw_content_hash  # populated with text hash

    claims = list_nodes(DescriptiveClaim, data_root)
    assert len(claims) == 2
    evidence = list_nodes(Evidence, data_root)
    assert len(evidence) == 2

    # 2 ingest + 1 linker = 3 total LLM calls. The linker fires exactly once.
    assert len(sdk.messages.calls) == 3


def test_ingest_dir_skips_directives_subpath(
    runner: CliRunner,
    data_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Files under a directives/ or directives-ai/ subdir must never reach the LLM."""
    saved = tmp_path / "saved"
    saved.mkdir()
    (saved / "directives").mkdir()
    _write_html_article(saved / "directives" / "leak.html")
    _write_html_article(saved / "good.html")

    payloads = [
        _make_ingest_payload("good_only", "claim_good"),
        _LINKER_PAYLOAD,
    ]
    sdk = _install_fake_sequence(monkeypatch, payloads)

    result = runner.invoke(app, ["ingest:dir", str(saved)])
    assert result.exit_code == 0, result.output

    sources = list_nodes(Source, data_root)
    assert {s.id for s in sources} == {"src_good_only"}

    # 1 ingest (good only) + 1 linker = 2 calls. leak.html never reached the LLM.
    assert len(sdk.messages.calls) == 2


def test_ingest_dir_dedupes_identical_content(
    runner: CliRunner,
    data_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved = tmp_path / "saved"
    saved.mkdir()
    html = (
        "<html><body>"
        + "".join(f"<p>identical paragraph {i}.</p>" for i in range(10))
        + "</body></html>"
    )
    (saved / "a.html").write_text(html, encoding="utf-8")
    (saved / "b.html").write_text(html, encoding="utf-8")

    payloads = [
        _make_ingest_payload("identical", "claim_identical"),
        _LINKER_PAYLOAD,
    ]
    _install_fake_sequence(monkeypatch, payloads)

    result = runner.invoke(app, ["ingest:dir", str(saved)])
    assert result.exit_code == 0, result.output
    assert "duplicate content" in result.output.lower()

    sources = list_nodes(Source, data_root)
    assert {s.id for s in sources} == {"src_identical"}


def test_ingest_dir_continues_past_per_file_failure(
    runner: CliRunner,
    data_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bad LLM response for one file shouldn't poison the whole batch."""
    saved = tmp_path / "saved"
    saved.mkdir()
    # Distinct body_tag values so the two files have distinct content hashes
    # (the batch dedupes by sha256, which would otherwise eat the second file).
    _write_html_article(saved / "a_first.html", body_tag="first")
    _write_html_article(saved / "b_second.html", body_tag="second")

    broken_payload = json.dumps(
        {
            "source": {
                "id_slug": "broken",
                "source_kind": "press",
                "title": "broken",
                "authors": [],
                "published_at": "",
                "reliability": 0.5,
                "notes": "",
            },
            "claims": [{"id_slug": "broken_claim", "text": "x", "confidence": 0.5}],
            "evidence": [
                {
                    "claim_idx": 99,  # out of range --- forces Exit(1) in _ingest_extracted
                    "locator": "",
                    "quote": "",
                    "method_tag": "journalistic_report",
                    "supports": "support",
                    "weight": 0.5,
                },
            ],
        }
    )
    payloads = [
        broken_payload,
        _make_ingest_payload("second_ok", "claim_second"),
        _LINKER_PAYLOAD,
    ]
    _install_fake_sequence(monkeypatch, payloads)

    result = runner.invoke(app, ["ingest:dir", str(saved)])
    assert result.exit_code == 0, result.output

    sources = list_nodes(Source, data_root)
    assert {s.id for s in sources} == {"src_second_ok"}


def test_ingest_dir_bails_on_empty_directory(
    runner: CliRunner,
    data_root: Path,
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(app, ["ingest:dir", str(empty)])
    assert result.exit_code == 1
    assert "no supported files" in result.output


def test_ingest_dir_rejects_non_directory(
    runner: CliRunner,
    data_root: Path,
    tmp_path: Path,
) -> None:
    stray = tmp_path / "stray.html"
    stray.write_text("<html></html>", encoding="utf-8")
    result = runner.invoke(app, ["ingest:dir", str(stray)])
    assert result.exit_code == 1
    assert "not a directory" in result.output


def test_ingest_dir_skips_html_with_too_few_paragraphs(
    runner: CliRunner,
    data_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTML precheck still applies on the file path --- a saved JS shell gets skipped."""
    saved = tmp_path / "saved"
    saved.mkdir()
    (saved / "shell.html").write_text(
        "<html><body><p>only one paragraph</p></body></html>", encoding="utf-8"
    )
    _write_html_article(saved / "real.html")

    payloads = [
        _make_ingest_payload("real_only", "claim_real"),
        _LINKER_PAYLOAD,
    ]
    sdk = _install_fake_sequence(monkeypatch, payloads)

    result = runner.invoke(app, ["ingest:dir", str(saved)])
    assert result.exit_code == 0, result.output
    assert "precheck failed" in result.output

    sources = list_nodes(Source, data_root)
    assert {s.id for s in sources} == {"src_real_only"}
    # shell.html skipped pre-LLM --- 1 ingest + 1 linker = 2 calls.
    assert len(sdk.messages.calls) == 2
