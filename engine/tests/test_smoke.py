"""Smoke tests: package imports, CLI registers, version is exposed."""

from __future__ import annotations

from typer.testing import CliRunner

import afls
from afls.cli import app


def test_version_exposed() -> None:
    assert afls.__version__ == "0.0.1"


def test_cli_version_command() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "afls 0.0.1" in result.stdout
