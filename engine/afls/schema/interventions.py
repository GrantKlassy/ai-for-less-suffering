"""Interventions, friction layers (things that resist them), and harm layers (costs of success)."""

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


class HarmLayer(BaseNode):
    """A counter-suffering vector the intervention imposes *if it succeeds*.

    Distinct from FrictionLayer: friction is what slows the intervention (grid,
    capex, regulation). Harm is what the intervention *costs* when it lands ---
    water, land, extraction, displacement, concentration, lock-in. Operator-scored
    so the tool never infers a suffering number from priors.
    """

    kind: str = Field(default="harm_layer", frozen=True)
    name: str = Field(min_length=1)
    description: str = Field(default="")


class Intervention(BaseNode):
    """A proposed action. Scored against friction layers and harm layers.

    Friction and harm share polarity: 1 = unblocked / no harm, 0 = fully
    blocked / maximum harm. Keeping the polarity aligned lets a future composite
    read as leverage * mean(friction) * mean(harm) without sign flips.
    """

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
    harm_scores: dict[NodeRef, float] = Field(
        default_factory=dict,
        description="Map of harm_layer_id -> harm robustness (0=maximum harm, 1=no harm).",
    )
