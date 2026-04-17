"""Cross-layer invariants between data/ (engine-owned) and src/ (presentation).

The engine's Pydantic schema forbids extra fields, so emoji-in-YAML is caught
at load time. This test catches the reverse: a CAMP_EMOJI map in
src/lib/graph.ts that drifts from the set of camp_*.yaml files under data/.

Belongs to `task check` (cross-layer invariant), not `task engine:test`
(schema semantics). Failure blocks pre-push via lefthook.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CAMPS_DIR = REPO_ROOT / "data" / "camps"
GRAPH_TS = REPO_ROOT / "src" / "lib" / "graph.ts"


def _camp_ids_from_data() -> set[str]:
    return {p.stem for p in CAMPS_DIR.glob("camp_*.yaml")}


def _camp_emoji_keys_from_graph_ts() -> set[str]:
    text = GRAPH_TS.read_text(encoding="utf-8")
    block_match = re.search(
        r"CAMP_EMOJI\s*:\s*Record<string,\s*string>\s*=\s*\{([^}]*)\}",
        text,
        re.DOTALL,
    )
    if block_match is None:
        raise AssertionError(
            "Could not locate CAMP_EMOJI block in src/lib/graph.ts --- "
            "refactor likely changed the shape; update this test."
        )
    return set(re.findall(r"(camp_[a-z_]+)\s*:", block_match.group(1)))


def test_camp_emoji_matches_camp_data() -> None:
    data_ids = _camp_ids_from_data()
    emoji_ids = _camp_emoji_keys_from_graph_ts()

    missing = data_ids - emoji_ids
    stale = emoji_ids - data_ids

    assert not missing, (
        f"CAMP_EMOJI missing entries for camps in data/camps/: {sorted(missing)}. "
        f"Add them to src/lib/graph.ts."
    )
    assert not stale, (
        f"CAMP_EMOJI has stale entries (no matching camp YAML): {sorted(stale)}. "
        f"Remove them from src/lib/graph.ts."
    )


def test_no_presentation_fields_in_camp_yaml() -> None:
    """Pydantic extra='forbid' already enforces this at load time, but check
    explicitly so the failure message points at the layering rule, not at a
    generic schema error."""
    offenders: list[tuple[str, str]] = []
    for p in CAMPS_DIR.glob("camp_*.yaml"):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for presentation_field in ("emoji", "color", "icon"):
            if presentation_field in data:
                offenders.append((p.name, presentation_field))

    assert not offenders, (
        "Camp YAML contains presentation fields --- presentation belongs in "
        f"src/lib/graph.ts, not data/camps/: {offenders}"
    )
