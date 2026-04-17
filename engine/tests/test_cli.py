"""CLI tests: driven via typer's CliRunner; data_dir/db_path rerouted to tmp_path."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from afls.cli import app
from afls.schema import (
    AxiomFamily,
    Bridge,
    Camp,
    DescriptiveClaim,
    FrictionLayer,
    Intervention,
    InterventionKind,
    NormativeClaim,
)
from afls.storage import save_node


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "data"
    monkeypatch.setenv("AFLS_DATA_DIR", str(root))
    monkeypatch.setenv("AFLS_DB_PATH", str(tmp_path / "afls.db"))
    return root


def _write_fragment(tmp_path: Path, name: str, payload: dict[str, Any]) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(payload, sort_keys=True))
    return path


def test_version(runner: CliRunner) -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "afls" in result.output


def test_add_descriptive_claim(runner: CliRunner, data_root: Path, tmp_path: Path) -> None:
    fragment = _write_fragment(
        tmp_path,
        "claim.yaml",
        {"kind": "descriptive_claim", "text": "AI deployment accelerates.", "confidence": 0.8},
    )
    result = runner.invoke(app, ["add", str(fragment)])
    assert result.exit_code == 0, result.output
    yaml_files = list((data_root / "claims" / "descriptive").glob("*.yaml"))
    assert len(yaml_files) == 1


def test_add_normative_claim(runner: CliRunner, data_root: Path, tmp_path: Path) -> None:
    fragment = _write_fragment(
        tmp_path,
        "norm.yaml",
        {
            "kind": "normative_claim",
            "text": "AI should reduce suffering.",
            "axiom_family": "ea_80k",
        },
    )
    result = runner.invoke(app, ["add", str(fragment)])
    assert result.exit_code == 0, result.output
    assert len(list((data_root / "claims" / "normative").glob("*.yaml"))) == 1


def test_add_camp_uses_slug_id(runner: CliRunner, data_root: Path, tmp_path: Path) -> None:
    fragment = _write_fragment(tmp_path, "camp.yaml", {"kind": "camp", "name": "Anthropic"})
    result = runner.invoke(app, ["add", str(fragment)])
    assert result.exit_code == 0, result.output
    assert (data_root / "camps" / "camp_anthropic.yaml").exists()


def test_add_respects_explicit_id(runner: CliRunner, data_root: Path, tmp_path: Path) -> None:
    fragment = _write_fragment(
        tmp_path,
        "claim.yaml",
        {
            "id": "desc_manual",
            "kind": "descriptive_claim",
            "text": "x",
            "confidence": 0.5,
        },
    )
    result = runner.invoke(app, ["add", str(fragment)])
    assert result.exit_code == 0
    assert (data_root / "claims" / "descriptive" / "desc_manual.yaml").exists()


def test_add_slug_kind_missing_name_errors(
    runner: CliRunner, data_root: Path, tmp_path: Path
) -> None:
    fragment = _write_fragment(tmp_path, "camp.yaml", {"kind": "camp"})
    result = runner.invoke(app, ["add", str(fragment)])
    assert result.exit_code == 1
    assert "name" in result.output


def test_add_missing_kind_errors(runner: CliRunner, data_root: Path, tmp_path: Path) -> None:
    fragment = _write_fragment(tmp_path, "bad.yaml", {"text": "x"})
    result = runner.invoke(app, ["add", str(fragment)])
    assert result.exit_code == 1
    assert "kind" in result.output


def test_add_unknown_kind_errors(runner: CliRunner, data_root: Path, tmp_path: Path) -> None:
    fragment = _write_fragment(tmp_path, "bad.yaml", {"kind": "unknown_kind"})
    result = runner.invoke(app, ["add", str(fragment)])
    assert result.exit_code == 1
    assert "unknown_kind" in result.output


def test_add_validation_error_exits(
    runner: CliRunner, data_root: Path, tmp_path: Path
) -> None:
    fragment = _write_fragment(
        tmp_path,
        "bad.yaml",
        {"kind": "descriptive_claim", "text": "x", "confidence": 2.0},
    )
    result = runner.invoke(app, ["add", str(fragment)])
    assert result.exit_code == 1
    assert "validation" in result.output.lower()


def test_add_missing_file_errors(runner: CliRunner, data_root: Path, tmp_path: Path) -> None:
    result = runner.invoke(app, ["add", str(tmp_path / "does-not-exist.yaml")])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_list_empty(runner: CliRunner, data_root: Path) -> None:
    result = runner.invoke(app, ["list", "camp"])
    assert result.exit_code == 0
    assert "no camp" in result.output


def test_list_shows_nodes(runner: CliRunner, data_root: Path) -> None:
    save_node(Camp(id="camp_alpha", name="Alpha"), data_root)
    save_node(Camp(id="camp_beta", name="Beta"), data_root)
    result = runner.invoke(app, ["list", "camp"])
    assert result.exit_code == 0
    assert "camp_alpha" in result.output
    assert "camp_beta" in result.output


def test_list_unknown_kind_errors(runner: CliRunner, data_root: Path) -> None:
    result = runner.invoke(app, ["list", "bogus"])
    assert result.exit_code == 1


def test_show_by_id(runner: CliRunner, data_root: Path) -> None:
    save_node(Camp(id="camp_test", name="TestCamp"), data_root)
    result = runner.invoke(app, ["show", "camp_test"])
    assert result.exit_code == 0
    assert "camp_test" in result.output
    assert "TestCamp" in result.output


def test_show_missing_exits(runner: CliRunner, data_root: Path) -> None:
    result = runner.invoke(app, ["show", "camp_nonexistent"])
    assert result.exit_code == 1


def test_validate_empty_ok(runner: CliRunner, data_root: Path) -> None:
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0
    assert "0 nodes" in result.output


def test_validate_ok_with_nodes(runner: CliRunner, data_root: Path) -> None:
    claim = DescriptiveClaim(id="desc_a", text="a", confidence=0.5)
    save_node(claim, data_root)
    save_node(Camp(id="camp_a", name="A", held_descriptive=["desc_a"]), data_root)
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0


def test_validate_finds_broken_ref(runner: CliRunner, data_root: Path) -> None:
    save_node(
        Camp(id="camp_a", name="A", held_descriptive=["desc_missing"]),
        data_root,
    )
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 1
    assert "desc_missing" in result.output


def test_validate_catches_wrong_type_ref(runner: CliRunner, data_root: Path) -> None:
    claim = NormativeClaim(id="norm_a", text="a", axiom_family=AxiomFamily.POKER_EV)
    save_node(claim, data_root)
    save_node(Camp(id="camp_a", name="A", held_descriptive=["norm_a"]), data_root)
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 1
    assert "norm_a" in result.output


def test_validate_catches_bad_convergence(runner: CliRunner, data_root: Path) -> None:
    from afls.schema import Convergence

    save_node(Camp(id="camp_a", name="A"), data_root)
    save_node(Camp(id="camp_b", name="B"), data_root)
    save_node(
        Convergence(
            id="conv_a",
            intervention_id="intv_missing",
            camps=["camp_a", "camp_b"],
        ),
        data_root,
    )
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 1
    assert "intv_missing" in result.output


def test_validate_catches_bad_friction_score(
    runner: CliRunner, data_root: Path
) -> None:
    save_node(
        Intervention(
            id="intv_a",
            text="t",
            action_kind=InterventionKind.TECHNICAL,
            leverage_score=0.5,
            friction_scores={"friction_missing": 0.5},
        ),
        data_root,
    )
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 1
    assert "friction_missing" in result.output


def test_validate_passes_with_full_graph(runner: CliRunner, data_root: Path) -> None:
    save_node(FrictionLayer(id="friction_grid", name="Grid"), data_root)
    save_node(
        Intervention(
            id="intv_a",
            text="t",
            action_kind=InterventionKind.TECHNICAL,
            leverage_score=0.5,
            friction_scores={"friction_grid": 0.8},
        ),
        data_root,
    )
    save_node(Camp(id="camp_a", name="A"), data_root)
    save_node(Camp(id="camp_b", name="B"), data_root)
    save_node(
        Bridge(id="bridge_ab", from_camp="camp_a", to_camp="camp_b", translation="x"),
        data_root,
    )
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0


def test_reindex(runner: CliRunner, data_root: Path, tmp_path: Path) -> None:
    save_node(Camp(id="camp_a", name="A"), data_root)
    save_node(Camp(id="camp_b", name="B"), data_root)
    result = runner.invoke(app, ["reindex"])
    assert result.exit_code == 0
    assert "indexed 2" in result.output
    assert (tmp_path / "afls.db").exists()


def test_edit_updates_node(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_node(Camp(id="camp_test", name="Original"), data_root)

    def fake_editor(cmd: list[str], check: bool) -> subprocess.CompletedProcess[bytes]:
        tmp_file = Path(cmd[-1])
        with tmp_file.open() as handle:
            data = yaml.safe_load(handle)
        data["name"] = "Edited"
        with tmp_file.open("w") as handle:
            yaml.safe_dump(data, handle, sort_keys=True)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_editor)
    result = runner.invoke(app, ["edit", "camp_test"])
    assert result.exit_code == 0, result.output

    reloaded = yaml.safe_load(
        (data_root / "camps" / "camp_test.yaml").read_text()
    )
    assert reloaded["name"] == "Edited"


def test_edit_id_change_rejected(
    runner: CliRunner,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_node(Camp(id="camp_test", name="Original"), data_root)

    def fake_editor(cmd: list[str], check: bool) -> subprocess.CompletedProcess[bytes]:
        tmp_file = Path(cmd[-1])
        with tmp_file.open() as handle:
            data = yaml.safe_load(handle)
        data["id"] = "camp_renamed"
        with tmp_file.open("w") as handle:
            yaml.safe_dump(data, handle, sort_keys=True)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_editor)
    result = runner.invoke(app, ["edit", "camp_test"])
    assert result.exit_code == 1
    assert "immutable" in result.output


def test_edit_missing_exits(runner: CliRunner, data_root: Path) -> None:
    result = runner.invoke(app, ["edit", "camp_nonexistent"])
    assert result.exit_code == 1
