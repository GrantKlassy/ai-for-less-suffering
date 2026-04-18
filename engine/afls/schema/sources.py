"""Source nodes: citable things that back evidence.

A Source is a thing you can point at --- a paper, a filing, a dataset, a piece of
journalism, a primary document. It carries operator-scored reliability so the
evidence layer can reason about epistemic quality without collapsing it into the
claim's confidence number.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from afls.schema.base import BaseNode


class SourceKind(StrEnum):
    PAPER = "paper"
    DATASET = "dataset"
    FILING = "filing"
    PRESS = "press"
    PRIMARY_DOC = "primary_doc"
    BLOG = "blog"
    DASHBOARD = "dashboard"
    DIRECTIVE = "directive"


ProvenanceMethod = Literal[
    "httpx",
    "manual_paste",
    "directive_canonical",
    "directive_ephemeral",
]


class Provenance(BaseModel):
    """How a Source entered the graph, stamped at intake.

    `method` records the channel; `tool` the version of whatever wrote the YAML;
    `git_sha` pins the repo state at intake so reasoning downstream can replay the
    context the drafter saw; `raw_content_hash` is sha256 of the text passed to the
    LLM (or sha256 of the raw directive body for ephemeral capture). None only for
    methods where no raw content existed at intake time.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    method: ProvenanceMethod
    tool: str = Field(min_length=1)
    git_sha: str = Field(min_length=1)
    at: datetime
    raw_content_hash: str | None = None


RELIABILITY_PRIOR: dict[SourceKind, float] = {
    SourceKind.PRIMARY_DOC: 0.90,
    SourceKind.FILING: 0.90,
    SourceKind.DATASET: 0.88,
    SourceKind.PAPER: 0.82,
    SourceKind.DASHBOARD: 0.75,
    SourceKind.PRESS: 0.50,
    SourceKind.BLOG: 0.35,
    SourceKind.DIRECTIVE: 0.40,
}
"""Default reliability by source_kind. Used by `afls ingest` and as the center of
the kind-based credibility lint. Operator can override per-source in YAML; the
prior is the starting point, not the ceiling."""


LOW_TRUST_KINDS: frozenset[SourceKind] = frozenset(
    {SourceKind.PRESS, SourceKind.BLOG}
)
"""Source kinds that shouldn't be the sole backing for a high-confidence claim.
Used by `_confidence_lint` in `afls.cli`."""


class Source(BaseNode):
    """A citable thing a piece of evidence can point at.

    `reliability` is operator-authored, not computed. The tool records the score;
    the operator decides whether a Palantir 10-K, an IHME dataset, or an anonymous
    Intercept source deserves the number attached.
    """

    kind: str = Field(default="source", frozen=True)
    source_kind: SourceKind
    title: str = Field(min_length=1)
    url: str = Field(default="")
    authors: list[str] = Field(default_factory=list)
    published_at: str = Field(
        default="", description="Free-text date. Accepts 'YYYY', 'YYYY-MM', 'YYYY-MM-DD', or ''."
    )
    accessed_at: str = Field(default="")
    reliability: float = Field(ge=0.0, le=1.0)
    notes: str = Field(default="")
    provenance: Provenance | None = None
