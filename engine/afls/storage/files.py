"""YAML I/O. One file per node. Deterministic key ordering so diffs stay clean."""

from __future__ import annotations

from pathlib import Path

import yaml

from afls.schema import BaseNode
from afls.storage.registry import NODE_SUBDIRS


def _node_path(model: type[BaseNode], node_id: str, data_dir: Path) -> Path:
    subdir = NODE_SUBDIRS[model]
    return data_dir.joinpath(*subdir, f"{node_id}.yaml")


def save_node(node: BaseNode, data_dir: Path) -> Path:
    """Serialize `node` to YAML under the type-specific subdirectory. Return the written path."""
    path = _node_path(type(node), node.id, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = node.model_dump(mode="json")
    with path.open("w") as handle:
        yaml.safe_dump(payload, handle, sort_keys=True, default_flow_style=False)
    return path


def load_node[T: BaseNode](model: type[T], node_id: str, data_dir: Path) -> T:
    """Load and validate a node of type `model` by ID."""
    path = _node_path(model, node_id, data_dir)
    with path.open() as handle:
        data = yaml.safe_load(handle)
    return model.model_validate(data)


def list_nodes[T: BaseNode](model: type[T], data_dir: Path) -> list[T]:
    """Load every node of type `model`. Sorted by filename for determinism."""
    subdir = NODE_SUBDIRS[model]
    dir_path = data_dir.joinpath(*subdir)
    if not dir_path.exists():
        return []
    return [
        load_node(model, path.stem, data_dir) for path in sorted(dir_path.glob("*.yaml"))
    ]


def delete_node(model: type[BaseNode], node_id: str, data_dir: Path) -> None:
    """Remove a node's YAML file. Errors if it doesn't exist."""
    _node_path(model, node_id, data_dir).unlink()
