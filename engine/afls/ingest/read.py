"""Read a local file and extract its text for ingest.

Sibling of `fetch.py`, same contract shape. Where fetch hits the network, this
reads from disk --- used by the `ingest:dir` CLI command to pick up files the
user saved manually (curl with UA, browser save-as, SingleFile) after a URL
failed precheck or returned 403/paywall. The post-extract pipeline downstream
(precheck, LLM draft, persistence, linker) is unchanged; only the origin
differs, and the `Provenance.method` field records which channel was used.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pypdf import PdfReader

from afls.ingest.fetch import (
    MAX_TEXT_BYTES,
    count_paragraph_tags,
    extract_text,
    truncate_utf8,
)

FileKind = Literal["html", "pdf", "text"]

_HTML_SUFFIXES: frozenset[str] = frozenset({".html", ".htm"})
_PDF_SUFFIXES: frozenset[str] = frozenset({".pdf"})
_TEXT_SUFFIXES: frozenset[str] = frozenset({".txt", ".md"})
SUPPORTED_SUFFIXES: frozenset[str] = _HTML_SUFFIXES | _PDF_SUFFIXES | _TEXT_SUFFIXES


class UnsupportedFileType(ValueError):
    """Raised when a file's suffix doesn't map to any of the extractors below."""


@dataclass(frozen=True)
class ReadResult:
    """Output of `read_and_extract`, parity with `fetch_and_extract`'s tuple.

    `canonical_id` is `file://<relative-path>` and serves the same role as a URL
    downstream: it's what Source.url records and what the LLM sees as the
    source identifier. `paragraph_count` is populated for HTML so the caller
    can run the same precheck as the URL path; 0 for PDF/text, where the
    caller should use a non-empty-text floor instead.
    """

    canonical_id: str
    text: str
    sha256: str
    paragraph_count: int
    kind: FileKind


def read_and_extract(path: Path, *, root: Path) -> ReadResult:
    """Read a local file and extract text per its suffix.

    `root` is the directory the user pointed the walker at; the canonical_id is
    built relative to it so `data/*.yaml` stays portable (no absolute paths).
    Raises `UnsupportedFileType` for anything outside `SUPPORTED_SUFFIXES`.
    """
    suffix = path.suffix.lower()
    rel = path.resolve().relative_to(root.resolve())
    canonical_id = f"file://{rel.as_posix()}"

    if suffix in _HTML_SUFFIXES:
        raw_html = path.read_text(encoding="utf-8", errors="replace")
        paragraph_count = count_paragraph_tags(raw_html)
        text = truncate_utf8(extract_text(raw_html), MAX_TEXT_BYTES)
        kind: FileKind = "html"
    elif suffix in _PDF_SUFFIXES:
        text = truncate_utf8(_extract_pdf_text(path), MAX_TEXT_BYTES)
        paragraph_count = 0
        kind = "pdf"
    elif suffix in _TEXT_SUFFIXES:
        raw = path.read_text(encoding="utf-8", errors="replace")
        text = truncate_utf8(raw, MAX_TEXT_BYTES)
        paragraph_count = 0
        kind = "text"
    else:
        raise UnsupportedFileType(f"unsupported file type: {suffix!r} ({path})")

    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return ReadResult(
        canonical_id=canonical_id,
        text=text,
        sha256=sha256,
        paragraph_count=paragraph_count,
        kind=kind,
    )


def _extract_pdf_text(path: Path) -> str:
    """Concatenate page text, blank-line-separated. Empty for image-only PDFs."""
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        stripped = extracted.strip()
        if stripped:
            pages.append(stripped)
    return "\n\n".join(pages)
