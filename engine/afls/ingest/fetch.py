"""Fetch a URL and extract its visible text.

No third-party HTML parser. `html.parser` from stdlib, plus a small tag-skip set,
gets us 80% of the way on arbitrary news/blog/paper HTML. The LLM does the rest
(picks the title, extracts the actual claims). We just need to hand Claude a
bounded chunk of text that doesn't include nav/footer/script boilerplate.
"""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser

import httpx

_SKIP_TAGS: frozenset[str] = frozenset(
    {"script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form"}
)

DEFAULT_TIMEOUT_S: float = 15.0
"""httpx timeout for the fetch. Long enough for slow sites, short enough that a
hung host doesn't wedge the CLI."""

MAX_TEXT_BYTES: int = 60_000
"""Upper bound on text handed to the LLM. ~15k tokens; enough for a long-form
article. Articles larger than this get truncated at a UTF-8 boundary."""


class _TextExtractor(HTMLParser):
    """Collect visible text, skipping anything inside nav/script/style/etc."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    def text(self) -> str:
        return "\n".join(self._chunks)


def extract_text(html: str) -> str:
    """Strip scripts/nav/footer, return joined visible text."""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()


def _truncate_utf8(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def fetch_and_extract(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_S,
    max_bytes: int = MAX_TEXT_BYTES,
) -> tuple[str, str, str]:
    """Fetch a URL and return `(final_url, text, sha256_hex)`.

    Follows redirects. Raises `httpx.HTTPError` on fetch failure. Text is truncated
    at a UTF-8 boundary so the LLM call stays bounded regardless of article size.
    The hash is over the exact text passed to the LLM, so provenance can replay
    the input later.
    """
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
    text = _truncate_utf8(extract_text(response.text), max_bytes)
    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return str(response.url), text, sha256
