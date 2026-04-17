"""Maps node-kind strings to Pydantic models and YAML subdirectories."""

from __future__ import annotations

from afls.schema import (
    BaseNode,
    BlindSpot,
    Bridge,
    Camp,
    Convergence,
    DescriptiveClaim,
    FrictionLayer,
    HarmLayer,
    Intervention,
    NormativeClaim,
    Source,
    Warrant,
)

NODE_TYPES: dict[str, type[BaseNode]] = {
    "descriptive_claim": DescriptiveClaim,
    "normative_claim": NormativeClaim,
    "camp": Camp,
    "intervention": Intervention,
    "friction_layer": FrictionLayer,
    "harm_layer": HarmLayer,
    "bridge": Bridge,
    "convergence": Convergence,
    "blindspot": BlindSpot,
    "source": Source,
    "warrant": Warrant,
}

NODE_SUBDIRS: dict[type[BaseNode], tuple[str, ...]] = {
    DescriptiveClaim: ("claims", "descriptive"),
    NormativeClaim: ("claims", "normative"),
    Camp: ("camps",),
    Intervention: ("interventions",),
    FrictionLayer: ("friction_layers",),
    HarmLayer: ("harm_layers",),
    Bridge: ("bridges",),
    Convergence: ("convergences",),
    BlindSpot: ("blindspots",),
    Source: ("sources",),
    Warrant: ("warrants",),
}
