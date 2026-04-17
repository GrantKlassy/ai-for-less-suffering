"""Camps: clusters of agents characterized by the claims they hold."""

from __future__ import annotations

from pydantic import Field

from afls.schema.base import BaseNode, NodeRef


class Camp(BaseNode):
    """A coalition-logic unit. Holds descriptive + normative claims.

    Two camps can hold the same descriptive claim (convergence) and different
    normative claims (divergence). That's the whole point.
    """

    kind: str = Field(default="camp", frozen=True)
    name: str = Field(min_length=1)
    agents: list[str] = Field(default_factory=list, description="Real-world orgs/people/movements.")
    held_descriptive: list[NodeRef] = Field(default_factory=list)
    held_normative: list[NodeRef] = Field(default_factory=list)
    summary: str = Field(default="", description="One-line operator characterization.")
