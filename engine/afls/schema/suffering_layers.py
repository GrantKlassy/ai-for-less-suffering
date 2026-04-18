"""Suffering layers --- the numerator. What an intervention *relieves* if it lands.

Disjoint from HarmLayer on purpose. Harm mixes welfare harms (displacement) with
structural harms (lock-in, concentration); suffering is first-person, categorical,
and scored in the opposite direction of cost. Without this layer the engine can
only minimize cost, which is not the same thing as reducing suffering per unit
compute.
"""

from __future__ import annotations

from pydantic import Field

from afls.schema.base import BaseNode


class SufferingLayer(BaseNode):
    """A category of first-person suffering an intervention can reduce.

    Seeded from the global-burden literature: disease burden, extreme poverty,
    preventable mortality, mental-health burden, education access, animal
    suffering. Operator-scored; the tool never infers a suffering number from
    priors.

    Polarity convention matches FrictionLayer/HarmLayer: 1 = maximum reduction,
    0 = no reduction. "Higher is better" holds across every layer scored on an
    Intervention so a future composite reads without sign flips.
    """

    kind: str = Field(default="suffering_layer", frozen=True)
    name: str = Field(min_length=1)
    description: str = Field(default="")
