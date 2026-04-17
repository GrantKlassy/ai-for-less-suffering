"""Runtime paths and environment. Central here so the CLI, storage, and tests agree."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Return the repo root by walking upward for a directory containing `directives-ai`."""
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / "directives-ai").is_dir():
            return candidate
    raise RuntimeError(
        "Could not locate repo root (no ancestor contains `directives-ai/`). "
        "Run afls from within the ai-for-less-suffering checkout."
    )


def data_dir() -> Path:
    """Where canonical YAML nodes live. Override via AFLS_DATA_DIR."""
    override = os.environ.get("AFLS_DATA_DIR")
    if override:
        return Path(override).resolve()
    return repo_root() / "data"


def db_path() -> Path:
    """Where the regenerable SQLite index lives. Override via AFLS_DB_PATH."""
    override = os.environ.get("AFLS_DB_PATH")
    if override:
        return Path(override).resolve()
    return data_dir() / "afls.db"


def public_output_dir() -> Path:
    """Where shaped engine outputs land for Astro to render."""
    return repo_root() / "public-output"
