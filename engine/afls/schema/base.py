"""Base class for every node in the typed graph."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

NodeRef = str
"""String ID referencing another node. Resolution happens in the storage layer, not here."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


class BaseNode(BaseModel):
    """Every typed-graph node shares these fields. Extra fields are forbidden."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    id: str
    kind: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    provenance_url: str | None = None
