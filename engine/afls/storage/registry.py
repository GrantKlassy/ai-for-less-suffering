"""Maps node-kind strings to Pydantic models and YAML subdirectories."""

from __future__ import annotations

from afls.schema import (
    BaseNode,
    BlindSpot,
    Bridge,
    Camp,
    Convergence,
    DescriptiveClaim,
    Evidence,
    FrictionLayer,
    HarmLayer,
    Intervention,
    NormativeClaim,
    Source,
    SufferingLayer,
)

NODE_TYPES: dict[str, type[BaseNode]] = {
    "descriptive_claim": DescriptiveClaim,
    "normative_claim": NormativeClaim,
    "camp": Camp,
    "intervention": Intervention,
    "friction_layer": FrictionLayer,
    "harm_layer": HarmLayer,
    "suffering_layer": SufferingLayer,
    "bridge": Bridge,
    "convergence": Convergence,
    "blindspot": BlindSpot,
    "source": Source,
    "evidence": Evidence,
}

NODE_SUBDIRS: dict[type[BaseNode], tuple[str, ...]] = {
    DescriptiveClaim: ("claims", "descriptive"),
    NormativeClaim: ("claims", "normative"),
    Camp: ("camps",),
    Intervention: ("interventions",),
    FrictionLayer: ("friction_layers",),
    HarmLayer: ("harm_layers",),
    SufferingLayer: ("suffering_layers",),
    Bridge: ("bridges",),
    Convergence: ("convergences",),
    BlindSpot: ("blindspots",),
    Source: ("sources",),
    Evidence: ("evidence",),
}
