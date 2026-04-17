"""Content-independent ID generation. Random hex for internal IDs; slug for human-facing ones."""

from __future__ import annotations

import re
import secrets


def new_id(prefix: str) -> str:
    """Return a fresh random ID of the form `<prefix>_<6-hex>`."""
    return f"{prefix}_{secrets.token_hex(3)}"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug_id(prefix: str, name: str) -> str:
    """Return a deterministic slug ID of the form `<prefix>_<slug>`.

    Used for nodes with unique human-facing names (camps, friction layers).
    """
    slug = _SLUG_RE.sub("-", name.lower()).strip("-")
    if not slug:
        raise ValueError(f"cannot slug-ify empty name: {name!r}")
    return f"{prefix}_{slug}"
