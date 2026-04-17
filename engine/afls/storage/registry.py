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
    Intervention,
    NormativeClaim,
)

NODE_TYPES: dict[str, type[BaseNode]] = {
    "descriptive_claim": DescriptiveClaim,
    "normative_claim": NormativeClaim,
    "camp": Camp,
    "intervention": Intervention,
    "friction_layer": FrictionLayer,
    "bridge": Bridge,
    "convergence": Convergence,
    "blindspot": BlindSpot,
}

NODE_SUBDIRS: dict[type[BaseNode], tuple[str, ...]] = {
    DescriptiveClaim: ("claims", "descriptive"),
    NormativeClaim: ("claims", "normative"),
    Camp: ("camps",),
    Intervention: ("interventions",),
    FrictionLayer: ("friction_layers",),
    Bridge: ("bridges",),
    Convergence: ("convergences",),
    BlindSpot: ("blindspots",),
}
