"""Claim nodes: the descriptive/normative split is enforced here."""

from __future__ import annotations

from pydantic import Field

from afls.schema.base import BaseNode


class DescriptiveClaim(BaseNode):
    """A factual assertion about the world. Never carries a value judgment.

    Provenance lives on Evidence nodes, not here. `confidence` is the operator's
    posterior after reading the evidence attached to this claim.
    """

    kind: str = Field(default="descriptive_claim", frozen=True)
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class NormativeClaim(BaseNode):
    """A value statement. Camps that hold it declare so on the camp side; this
    node does not self-label. Axiom families are a forthcoming top-level node
    type; this schema is deliberately minimal until that lands.
    """

    kind: str = Field(default="normative_claim", frozen=True)
    text: str = Field(min_length=1)
