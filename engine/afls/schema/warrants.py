"""Warrant nodes: Source-to-Claim edges with a method tag and a support stance.

A Warrant is one link in the reasoning chain: *this source, by this method, supports
(or contradicts, or qualifies) this claim*. Multiple warrants attaching to one claim
makes the epistemic apparatus visible --- a reader can see what the confidence number
is backed by, and whether the backing is direct measurement or expert estimate or
contested journalism.

Method lives here as a field (not its own node) because methods don't have identity
you re-reference across the graph; they are a property of *how this source warrants
this claim*.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from afls.schema.base import BaseNode, NodeRef


class MethodTag(StrEnum):
    DIRECT_MEASUREMENT = "direct_measurement"
    EXPERT_ESTIMATE = "expert_estimate"
    TRIANGULATION = "triangulation"
    JOURNALISTIC_REPORT = "journalistic_report"
    PRIMARY_TESTIMONY = "primary_testimony"
    MODELED_PROJECTION = "modeled_projection"
    LEAKED_DOCUMENT = "leaked_document"


class Support(StrEnum):
    SUPPORT = "support"
    CONTRADICT = "contradict"
    QUALIFY = "qualify"


class Warrant(BaseNode):
    """One Source-Claim edge. Reasoning chains are queries over these."""

    kind: str = Field(default="warrant", frozen=True)
    claim_id: NodeRef
    source_id: NodeRef
    locator: str = Field(
        default="",
        description="Page, section, figure, table, or timestamp pointing into the source.",
    )
    quote: str = Field(
        default="", description="Short excerpt. Omit when ToS or paywall constrains copying."
    )
    method_tag: MethodTag
    supports: Support = Support.SUPPORT
    weight: float = Field(
        ge=0.0,
        le=1.0,
        description="Local contribution of this warrant to the claim. Operator-authored.",
    )
