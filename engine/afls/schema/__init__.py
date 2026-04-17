"""Pydantic schema for the afls typed graph. Every node type here is lifted from MANIFESTO.md."""

from afls.schema.axioms import AxiomFamily
from afls.schema.base import BaseNode, NodeRef
from afls.schema.camps import Camp
from afls.schema.claims import DescriptiveClaim, NormativeClaim
from afls.schema.ids import new_id, slug_id
from afls.schema.interventions import FrictionLayer, HarmLayer, Intervention, InterventionKind
from afls.schema.relations import BlindSpot, Bridge, Convergence
from afls.schema.sources import Source, SourceKind
from afls.schema.warrants import MethodTag, Support, Warrant

__all__ = [
    "AxiomFamily",
    "BaseNode",
    "BlindSpot",
    "Bridge",
    "Camp",
    "Convergence",
    "DescriptiveClaim",
    "FrictionLayer",
    "HarmLayer",
    "Intervention",
    "InterventionKind",
    "MethodTag",
    "NodeRef",
    "NormativeClaim",
    "Source",
    "SourceKind",
    "Support",
    "Warrant",
    "new_id",
    "slug_id",
]
