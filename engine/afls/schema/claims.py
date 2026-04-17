"""Claim nodes: the descriptive/normative split is enforced here."""

from __future__ import annotations

from pydantic import Field

from afls.schema.axioms import AxiomFamily
from afls.schema.base import BaseNode


class DescriptiveClaim(BaseNode):
    """A factual assertion about the world. Never carries a value judgment.

    Provenance lives on Warrant nodes, not here. `confidence` is the operator's
    posterior after reading the warrants attached to this claim.
    """

    kind: str = Field(default="descriptive_claim", frozen=True)
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class NormativeClaim(BaseNode):
    """A value statement. Tagged with the axiom family it derives from."""

    kind: str = Field(default="normative_claim", frozen=True)
    text: str = Field(min_length=1)
    axiom_family: AxiomFamily
    axiom_detail: str = Field(default="", description="Specific normative tradition or reasoning.")
