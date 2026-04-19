"""Live-corpus linkage assertions.

`test_cli.py` proves the validator *can* catch broken refs on synthetic inputs.
These tests prove the current `data/` directory is actually clean --- every
NodeRef in committed YAML resolves to the expected kind. If a PR merges a
YAML file with a dangling ref, CI fails here instead of waiting for the next
`afls validate` run.

One test per ref-carrying surface (A1-A10 from the plan). Each builds its
own id-to-kind index rather than sharing one --- keeps failures localized so
a regression in e.g. Evidence linkage does not mask one in Convergence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from afls.config import data_dir
from afls.schema import (
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
from afls.storage import NODE_TYPES, list_nodes


@pytest.fixture(scope="module")
def root() -> Path:
    return data_dir()


@pytest.fixture(scope="module")
def id_to_kind(root: Path) -> dict[str, str]:
    """One pass over every YAML, keyed by id. Used by every ref check below."""
    index: dict[str, str] = {}
    for kind, model in NODE_TYPES.items():
        for node in list_nodes(model, root):
            index[node.id] = kind
    return index


def _assert_ref(
    index: dict[str, str],
    owner_id: str,
    field: str,
    ref_id: str,
    expected_kind: str,
) -> None:
    """Fail fast with an operator-readable message if a ref misses or miskinds."""
    found = index.get(ref_id)
    assert found is not None, f"{owner_id}.{field}: unknown id {ref_id!r}"
    assert found == expected_kind, (
        f"{owner_id}.{field}: {ref_id!r} is {found}, expected {expected_kind}"
    )


def test_a1_camp_held_descriptive_refs_resolve(
    root: Path, id_to_kind: dict[str, str]
) -> None:
    for camp in list_nodes(Camp, root):
        for ref in camp.held_descriptive:
            _assert_ref(id_to_kind, camp.id, "held_descriptive", ref, "descriptive_claim")


def test_a2_camp_held_normative_refs_resolve(
    root: Path, id_to_kind: dict[str, str]
) -> None:
    for camp in list_nodes(Camp, root):
        for ref in camp.held_normative:
            _assert_ref(id_to_kind, camp.id, "held_normative", ref, "normative_claim")


def test_a3_camp_disputed_evidence_refs_resolve(
    root: Path, id_to_kind: dict[str, str]
) -> None:
    for camp in list_nodes(Camp, root):
        for ref in camp.disputed_evidence:
            _assert_ref(id_to_kind, camp.id, "disputed_evidence", ref, "evidence")


def test_a4_evidence_claim_id_resolves(
    root: Path, id_to_kind: dict[str, str]
) -> None:
    for evidence in list_nodes(Evidence, root):
        _assert_ref(
            id_to_kind, evidence.id, "claim_id", evidence.claim_id, "descriptive_claim"
        )


def test_a5_evidence_source_id_resolves(
    root: Path, id_to_kind: dict[str, str]
) -> None:
    for evidence in list_nodes(Evidence, root):
        _assert_ref(id_to_kind, evidence.id, "source_id", evidence.source_id, "source")


def test_a6_intervention_friction_scores_keys_are_friction_layers(
    root: Path, id_to_kind: dict[str, str]
) -> None:
    for intv in list_nodes(Intervention, root):
        for ref in intv.friction_scores:
            _assert_ref(id_to_kind, intv.id, "friction_scores", ref, "friction_layer")


def test_a7_intervention_harm_scores_keys_are_harm_layers(
    root: Path, id_to_kind: dict[str, str]
) -> None:
    for intv in list_nodes(Intervention, root):
        for ref in intv.harm_scores:
            _assert_ref(id_to_kind, intv.id, "harm_scores", ref, "harm_layer")


def test_a8_intervention_suffering_scores_keys_are_suffering_layers(
    root: Path, id_to_kind: dict[str, str]
) -> None:
    for intv in list_nodes(Intervention, root):
        for ref in intv.suffering_reduction_scores:
            _assert_ref(
                id_to_kind,
                intv.id,
                "suffering_reduction_scores",
                ref,
                "suffering_layer",
            )


def test_a9_bridge_endpoints_resolve_as_camps(
    root: Path, id_to_kind: dict[str, str]
) -> None:
    for bridge in list_nodes(Bridge, root):
        _assert_ref(id_to_kind, bridge.id, "from_camp", bridge.from_camp, "camp")
        _assert_ref(id_to_kind, bridge.id, "to_camp", bridge.to_camp, "camp")


def test_a10_convergence_refs_resolve(
    root: Path, id_to_kind: dict[str, str]
) -> None:
    """Convergence carries three independent ref surfaces; check each."""
    for conv in list_nodes(Convergence, root):
        _assert_ref(
            id_to_kind,
            conv.id,
            "intervention_id",
            conv.intervention_id,
            "intervention",
        )
        for ref in conv.camps:
            _assert_ref(id_to_kind, conv.id, "camps", ref, "camp")
        for camp_id, norm_id in conv.divergent_reasons.items():
            _assert_ref(
                id_to_kind, conv.id, "divergent_reasons.key", camp_id, "camp"
            )
            _assert_ref(
                id_to_kind,
                conv.id,
                "divergent_reasons.value",
                norm_id,
                "normative_claim",
            )


def test_blindspot_flagged_camp_resolves(
    root: Path, id_to_kind: dict[str, str]
) -> None:
    """Coverage for the ref the plan credits to the existing validator;
    belt-and-suspenders, since blindspot is a new node kind and blast radius
    of a miss is high."""
    for blindspot in list_nodes(BlindSpot, root):
        _assert_ref(
            id_to_kind,
            blindspot.id,
            "flagged_camp_id",
            blindspot.flagged_camp_id,
            "camp",
        )


def test_every_indexed_id_is_a_known_kind(id_to_kind: dict[str, str]) -> None:
    """Sanity floor: the registry-built index can't carry an unknown kind,
    but if NODE_TYPES ever acquires an alias, a duplicate index entry would
    silently let the assertions above pass. Assert tightness here."""
    for node_id, kind in id_to_kind.items():
        assert kind in NODE_TYPES, f"{node_id}: indexed as unknown kind {kind!r}"


def test_live_corpus_has_interesting_shape(
    root: Path, id_to_kind: dict[str, str]
) -> None:
    """If the corpus is empty, the tests above pass vacuously. Assert enough
    nodes exist that the above actually exercised something. Bounds are loose
    --- intent is 'not empty', not 'exactly N'."""
    assert len(id_to_kind) >= 20, (
        f"live corpus has {len(id_to_kind)} nodes --- linkage tests vacuous"
    )
    # And every class of thing the linkage tests check should exist at least once.
    for model in (
        Camp,
        DescriptiveClaim,
        NormativeClaim,
        Intervention,
        Source,
        Evidence,
        FrictionLayer,
        HarmLayer,
        SufferingLayer,
    ):
        assert list_nodes(model, root), (
            f"no {model.__name__} nodes in live corpus; a linkage test may have "
            "passed vacuously"
        )
