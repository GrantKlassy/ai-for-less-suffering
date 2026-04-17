"""Interventions (proposed actions) and friction layers (things that resist them)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from afls.schema.base import BaseNode, NodeRef


class InterventionKind(StrEnum):
    TECHNICAL = "technical"
    POLITICAL = "political"
    ECONOMIC = "economic"


class FrictionLayer(BaseNode):
    """A resistance dimension an intervention must survive.

    Seeded from MANIFESTO: grid, capex, regulation, enterprise-absorption,
    public-backlash.
    """

    kind: str = Field(default="friction_layer", frozen=True)
    name: str = Field(min_length=1)
    description: str = Field(default="")


class Intervention(BaseNode):
    """A proposed action. Scored against friction layers (higher = more robust)."""

    kind: str = Field(default="intervention", frozen=True)
    text: str = Field(min_length=1)
    action_kind: InterventionKind
    cost_estimate: str = Field(default="", description="Free-text cost/resource envelope.")
    leverage_score: float = Field(
        ge=0.0, le=1.0, description="Operator-authored leverage estimate."
    )
    friction_scores: dict[NodeRef, float] = Field(
        default_factory=dict,
        description="Map of friction_layer_id -> robustness score (0=blocked, 1=no friction).",
    )
