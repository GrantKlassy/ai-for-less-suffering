"""Source nodes: citable things that back warrants.

A Source is a thing you can point at --- a paper, a filing, a dataset, a piece of
journalism, a primary document. It carries operator-scored reliability so the
warrant layer can reason about epistemic quality without collapsing it into the
claim's confidence number.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from afls.schema.base import BaseNode


class SourceKind(StrEnum):
    PAPER = "paper"
    DATASET = "dataset"
    FILING = "filing"
    PRESS = "press"
    PRIMARY_DOC = "primary_doc"
    BLOG = "blog"
    DASHBOARD = "dashboard"


class Source(BaseNode):
    """A citable thing a warrant can point at.

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
