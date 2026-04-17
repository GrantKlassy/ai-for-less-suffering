"""SQLite index. Regenerable from YAML via `rebuild()`. Never the source of truth."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from afls.schema import BaseNode
from afls.storage.files import list_nodes
from afls.storage.registry import NODE_TYPES

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    return conn


def rebuild(data_dir: Path, db_path: Path) -> int:
    """Wipe and repopulate the SQLite index from YAML. Returns node count."""
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM nodes")
        count = 0
        for model in NODE_TYPES.values():
            for node in list_nodes(model, data_dir):
                conn.execute(
                    "INSERT INTO nodes (id, kind, data, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        node.id,
                        node.kind,
                        node.model_dump_json(),
                        node.created_at.isoformat(),
                        node.updated_at.isoformat(),
                    ),
                )
                count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def get_by_id(db_path: Path, node_id: str) -> BaseNode | None:
    """Look up any node by ID. Returns the concrete subclass or None if missing."""
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT kind, data FROM nodes WHERE id = ?", (node_id,))
        row = cur.fetchone()
        if row is None:
            return None
        kind, data = row
        model = NODE_TYPES[kind]
        return model.model_validate_json(data)
    finally:
        conn.close()


def list_by_kind[T: BaseNode](db_path: Path, model: type[T]) -> list[T]:
    """Return every node of the given model type."""
    kind = _kind_of_type(model)
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT data FROM nodes WHERE kind = ? ORDER BY id", (kind,))
        return [model.model_validate_json(row[0]) for row in cur.fetchall()]
    finally:
        conn.close()


def _kind_of_type(model: type[BaseNode]) -> str:
    for kind, cls in NODE_TYPES.items():
        if cls is model:
            return kind
    raise KeyError(f"unknown model {model}")
