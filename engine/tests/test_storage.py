"""Storage tests: YAML round-trip, SQLite rebuild, cross-type queries."""

from __future__ import annotations

from pathlib import Path

import pytest

from afls.schema import (
    AxiomFamily,
    Camp,
    DescriptiveClaim,
    Intervention,
    InterventionKind,
    NormativeClaim,
    new_id,
    slug_id,
)
from afls.storage import (
    delete_node,
    get_by_id,
    list_by_kind,
    list_nodes,
    load_node,
    rebuild,
    save_node,
)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "afls.db"


def test_save_and_load_descriptive_claim(data_dir: Path) -> None:
    claim = DescriptiveClaim(
        id=new_id("desc"),
        text="AI deployment is accelerating.",
        confidence=0.9,
    )
    path = save_node(claim, data_dir)
    assert path.exists()
    loaded = load_node(DescriptiveClaim, claim.id, data_dir)
    assert loaded.text == claim.text
    assert loaded.confidence == 0.9


def test_save_writes_sorted_keys(data_dir: Path) -> None:
    claim = DescriptiveClaim(id=new_id("desc"), text="x", confidence=0.5)
    path = save_node(claim, data_dir)
    contents = path.read_text()
    top_level = [
        line.split(":")[0]
        for line in contents.splitlines()
        if line and not line.startswith(" ")
    ]
    assert top_level == sorted(top_level), f"YAML keys not alphabetically sorted: {top_level}"


def test_list_nodes_returns_sorted(data_dir: Path) -> None:
    claims = [
        DescriptiveClaim(id="desc_bbb", text="b", confidence=0.5),
        DescriptiveClaim(id="desc_aaa", text="a", confidence=0.5),
        DescriptiveClaim(id="desc_ccc", text="c", confidence=0.5),
    ]
    for c in claims:
        save_node(c, data_dir)
    loaded = list_nodes(DescriptiveClaim, data_dir)
    assert [c.id for c in loaded] == ["desc_aaa", "desc_bbb", "desc_ccc"]


def test_list_nodes_empty_when_dir_missing(data_dir: Path) -> None:
    assert list_nodes(DescriptiveClaim, data_dir) == []


def test_delete_node(data_dir: Path) -> None:
    claim = DescriptiveClaim(id=new_id("desc"), text="x", confidence=0.5)
    save_node(claim, data_dir)
    delete_node(DescriptiveClaim, claim.id, data_dir)
    assert list_nodes(DescriptiveClaim, data_dir) == []


def test_rebuild_indexes_all_types(data_dir: Path, db_path: Path) -> None:
    claim_d = DescriptiveClaim(id=new_id("desc"), text="AI is accelerating.", confidence=0.9)
    claim_n = NormativeClaim(
        id=new_id("norm"),
        text="AI should reduce suffering.",
        axiom_family=AxiomFamily.EA_80K,
    )
    camp = Camp(
        id=slug_id("camp", "Anthropic"),
        name="Anthropic",
        held_descriptive=[claim_d.id],
        held_normative=[claim_n.id],
    )
    intv = Intervention(
        id=new_id("intv"),
        text="Expand frontier-lab headcount.",
        action_kind=InterventionKind.ECONOMIC,
        leverage_score=0.7,
    )
    for node in (claim_d, claim_n, camp, intv):
        save_node(node, data_dir)

    count = rebuild(data_dir, db_path)
    assert count == 4


def test_get_by_id_returns_correct_subclass(data_dir: Path, db_path: Path) -> None:
    claim = DescriptiveClaim(id=new_id("desc"), text="x", confidence=0.5)
    save_node(claim, data_dir)
    rebuild(data_dir, db_path)
    loaded = get_by_id(db_path, claim.id)
    assert isinstance(loaded, DescriptiveClaim)
    assert loaded.text == "x"


def test_get_by_id_returns_none_when_missing(data_dir: Path, db_path: Path) -> None:
    rebuild(data_dir, db_path)
    assert get_by_id(db_path, "desc_nonexistent") is None


def test_list_by_kind_filters_correctly(data_dir: Path, db_path: Path) -> None:
    d1 = DescriptiveClaim(id="desc_aaa", text="a", confidence=0.5)
    d2 = DescriptiveClaim(id="desc_bbb", text="b", confidence=0.5)
    n1 = NormativeClaim(id="norm_ccc", text="c", axiom_family=AxiomFamily.POKER_EV)
    for node in (d1, d2, n1):
        save_node(node, data_dir)
    rebuild(data_dir, db_path)

    descs = list_by_kind(db_path, DescriptiveClaim)
    norms = list_by_kind(db_path, NormativeClaim)
    assert {d.id for d in descs} == {"desc_aaa", "desc_bbb"}
    assert {n.id for n in norms} == {"norm_ccc"}


def test_rebuild_is_idempotent(data_dir: Path, db_path: Path) -> None:
    claim = DescriptiveClaim(id=new_id("desc"), text="x", confidence=0.5)
    save_node(claim, data_dir)
    assert rebuild(data_dir, db_path) == 1
    assert rebuild(data_dir, db_path) == 1
    assert len(list_by_kind(db_path, DescriptiveClaim)) == 1
