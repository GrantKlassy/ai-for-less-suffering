"""Pydantic schema for the afls typed graph. Every node type here is lifted from MANIFESTO.md."""

from afls.schema.axioms import AxiomFamily
from afls.schema.base import BaseNode, NodeRef
from afls.schema.camps import Camp
from afls.schema.claims import DescriptiveClaim, NormativeClaim
from afls.schema.ids import new_id, slug_id
from afls.schema.interventions import FrictionLayer, Intervention, InterventionKind
from afls.schema.relations import BlindSpot, Bridge, Convergence

__all__ = [
    "AxiomFamily",
    "BaseNode",
    "BlindSpot",
    "Bridge",
    "Camp",
    "Convergence",
    "DescriptiveClaim",
    "FrictionLayer",
    "Intervention",
    "InterventionKind",
    "NodeRef",
    "NormativeClaim",
    "new_id",
    "slug_id",
]
