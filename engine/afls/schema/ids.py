"""Content-independent ID generation. Random hex for internal IDs; slug for human-facing ones."""

from __future__ import annotations

import hashlib
import re
import secrets


def new_id(prefix: str) -> str:
    """Return a fresh random ID of the form `<prefix>_<6-hex>`."""
    return f"{prefix}_{secrets.token_hex(3)}"


_SLUG_RE = re.compile(r"[^a-z0-9]+")
_WHITESPACE_RE = re.compile(r"\s+")


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.lower()).strip("-")
    if not slug:
        raise ValueError(f"cannot slug-ify empty value: {value!r}")
    return slug


def slug_id(prefix: str, name: str) -> str:
    """Return a deterministic slug ID of the form `<prefix>_<slug>`.

    Used for nodes with unique human-facing names (camps, friction layers).
    """
    return f"{prefix}_{_slugify(name)}"


def normalize_for_hash(value: str) -> str:
    """Normalize free-text content before hashing. Lowercased, whitespace-collapsed, stripped."""
    return _WHITESPACE_RE.sub(" ", value.lower().strip())


def content_hash(value: str) -> str:
    """Full hex sha256 over the normalized content. Stored on the node for introspection."""
    return hashlib.sha256(normalize_for_hash(value).encode("utf-8")).hexdigest()


def content_id(prefix: str, *, slug_parts: list[str], hashed: str) -> str:
    """Return a content-addressed ID of the form `<prefix>_<slug1>_<slug2>..._<h6>`.

    Same slug parts + same normalized `hashed` content → same ID. Used for
    auto-persisted relation nodes (Bridges, BlindSpots) so repeat runs dedupe
    rather than flood the graph with near-duplicates.
    """
    slugs = "_".join(_slugify(p) for p in slug_parts)
    h6 = content_hash(hashed)[:6]
    return f"{prefix}_{slugs}_{h6}"
