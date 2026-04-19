"""Schema-drift fixture: emit a JSON dump of every Python enum + the ID
prefix map, so the TS side (src/lib/schema-drift.test.ts) can assert parity.

The JSON is gitignored. pytest always overwrites it on run, so inside
`task check` (which runs engine tests before site tests) the file is always
current when vitest reads it. Outside that flow, the drift test has a clear
failure mode pointing at `task engine:test` as the prerequisite.

These tests also pin the Python-side shape so a Python-only rename is caught
here --- before the dump reaches vitest and produces a less-useful error.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import get_args

from afls import schema as afls_schema
from afls.cli import _ID_PREFIX, LAYER_EDGE_MIN_SCORE
from afls.schema.base import BaseNode
from afls.schema.evidence import MethodTag, Support
from afls.schema.interventions import InterventionKind
from afls.schema.sources import ProvenanceMethod, SourceKind

ENUMS_JSON_PATH = Path(__file__).parent / "_enums.json"


def _dump_enums() -> dict[str, object]:
    """Serialize every Python-side schema surface to a stable JSON shape."""
    return {
        "SourceKind": sorted(e.value for e in SourceKind),
        "MethodTag": sorted(e.value for e in MethodTag),
        "Support": sorted(e.value for e in Support),
        "InterventionKind": sorted(e.value for e in InterventionKind),
        "ProvenanceMethod": sorted(get_args(ProvenanceMethod)),
        "ID_PREFIX": dict(sorted(_ID_PREFIX.items())),
        "NodeKinds": sorted(_ID_PREFIX.keys()),
        "LAYER_EDGE_MIN_SCORE": LAYER_EDGE_MIN_SCORE,
    }


def test_dump_enums_json() -> None:
    """Always-overwrite the JSON so the TS side has a current snapshot."""
    data = _dump_enums()
    ENUMS_JSON_PATH.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    assert ENUMS_JSON_PATH.exists()


def test_source_kind_shape() -> None:
    """D1: SourceKind values are locked down."""
    values = [e.value for e in SourceKind]
    assert sorted(values) == [
        "blog",
        "dashboard",
        "dataset",
        "filing",
        "paper",
        "press",
        "primary_doc",
    ]


def test_method_tag_shape() -> None:
    """D2: MethodTag values are locked down."""
    values = [e.value for e in MethodTag]
    assert sorted(values) == [
        "direct_measurement",
        "expert_estimate",
        "journalistic_report",
        "leaked_document",
        "modeled_projection",
        "primary_testimony",
        "triangulation",
    ]


def test_support_shape() -> None:
    """D3: Support (evidence stance) values are locked down."""
    values = [e.value for e in Support]
    assert sorted(values) == ["contradict", "qualify", "support"]


def test_intervention_kind_shape() -> None:
    """D4: InterventionKind values are locked down."""
    values = [e.value for e in InterventionKind]
    assert sorted(values) == ["economic", "political", "technical"]


def test_provenance_method_shape() -> None:
    """D5: ProvenanceMethod (Literal alias) values are locked down."""
    values = list(get_args(ProvenanceMethod))
    assert sorted(values) == ["httpx", "manual_paste"]


def test_id_prefix_includes_coalition_kinds() -> None:
    """D6 (Python side): bridge/convergence/blindspot kinds must be registered."""
    assert _ID_PREFIX["bridge"] == "bridge"
    assert _ID_PREFIX["convergence"] == "conv"
    assert _ID_PREFIX["blindspot"] == "blind"


def test_id_prefix_covers_all_node_kinds() -> None:
    """D8 (Python side): ID_PREFIX is the Python-side NodeKind enumeration.

    When a new kind lands, it must be registered here or `afls validate` will
    not know how to resolve refs. Catching it in a dedicated test makes the
    failure explicit instead of deferred.
    """
    expected = {
        "camp",
        "descriptive_claim",
        "normative_claim",
        "intervention",
        "source",
        "evidence",
        "friction_layer",
        "harm_layer",
        "suffering_layer",
        "bridge",
        "convergence",
        "blindspot",
    }
    assert set(_ID_PREFIX.keys()) == expected


def test_layer_edge_min_score_value() -> None:
    """D9 (Python side): the pruning threshold is locked at 0.3.

    The value is mirrored in `src/lib/graph-data.ts`. Changing one without the
    other means the CLI warning and the homepage's edge-prune diverge: a
    warning fires for an edge the site still draws, or the site drops an edge
    the operator had no warning about.
    """
    assert LAYER_EDGE_MIN_SCORE == 0.3


def test_directives_not_wired_as_data() -> None:
    """D10: directives are slop that feeds the reasoner, not Source/Evidence.

    The storage layer resolves node paths through `NODE_SUBDIRS`. If any
    directive-adjacent path ever shows up there, directives become citable ---
    and the reasoner will happily cite Grant's own raw thoughts back to him
    as if they were primary evidence. Catch it here.
    """
    from afls.storage.registry import NODE_SUBDIRS

    forbidden = {"directives", "directives-ai"}
    for model, subdir in NODE_SUBDIRS.items():
        for segment in subdir:
            assert segment not in forbidden, (
                f"{model.__name__} routes through forbidden segment {segment!r}"
            )


def test_no_directive_paths_in_data_yaml() -> None:
    """D10 complement: no YAML file under `data/` mentions a directive path.

    Grep-style invariant. Catches the case where someone transcribes directive
    content into a Source's `notes` field or Evidence's `quote`, which would
    re-enter the reasoning loop and launder directives back in.
    """
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = repo_root / "data"
    forbidden_substrings = ("directives-ai/", "directives/", "directives-ai\\")
    offenders: list[tuple[Path, str]] = []
    for yaml_file in data_dir.rglob("*.yaml"):
        text = yaml_file.read_text(encoding="utf-8")
        for needle in forbidden_substrings:
            if needle in text:
                offenders.append((yaml_file, needle))
    assert offenders == [], (
        f"YAML under data/ references directive paths: {offenders}"
    )


def test_operator_prior_set_name_is_grant_brain() -> None:
    """D11: BRAIN.md never appears without the GRANT_ prefix.

    The operator prior set file is `directives-ai/GRANT_BRAIN.md`. An earlier
    rename left the stale literal `BRAIN.md` in prompts, YAML summaries, docs,
    and a test assertion. Catch any future reintroduction. `public-output/` is
    excluded --- historical analyses are frozen snapshots.
    """
    repo_root = Path(__file__).resolve().parents[2]
    pattern = re.compile(r"(?<!GRANT_)\bBRAIN\.md\b")
    scan_dirs = [
        repo_root / "engine",
        repo_root / "data",
        repo_root / "directives-ai",
    ]
    self_path = Path(__file__).resolve()
    offenders: list[tuple[str, int, str]] = []
    for root in scan_dirs:
        for suffix in ("*.py", "*.yaml", "*.md"):
            for path in root.rglob(suffix):
                if path.resolve() == self_path:
                    continue
                text = path.read_text(encoding="utf-8")
                for lineno, line in enumerate(text.splitlines(), start=1):
                    if pattern.search(line):
                        offenders.append(
                            (str(path.relative_to(repo_root)), lineno, line.strip())
                        )
    assert offenders == [], (
        f"BRAIN.md references without GRANT_ prefix: {offenders}"
    )


_TREE_LINE = re.compile(r"^((?:│   |    )*)[├└]── (.+)$")


def test_architecture_md_paths_exist() -> None:
    """D12: every path named in ARCHITECTURE.md's tree block resolves.

    Parses the ASCII tree, builds full paths by tracking indent depth, and
    asserts each one exists on disk. Descriptive entries (containing `*`,
    `+`, `{`, or internal spaces) are skipped --- they're wildcards or prose,
    not literal paths.
    """
    repo_root = Path(__file__).resolve().parents[2]
    arch_md = repo_root / "directives-ai" / "ARCHITECTURE.md"
    text = arch_md.read_text(encoding="utf-8")

    tree_lines: list[str] = []
    in_tree = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("ai-for-less-suffering/"):
            in_tree = True
            continue
        if in_tree:
            if stripped == "```":
                break
            tree_lines.append(line)

    assert tree_lines, "ARCHITECTURE.md tree block not found"

    stack: list[str] = []
    missing: list[tuple[str, Path]] = []
    for raw in tree_lines:
        line = raw.split("#", 1)[0].rstrip() if "#" in raw else raw.rstrip()
        if not line.strip():
            continue
        match = _TREE_LINE.match(line)
        if not match:
            continue
        prefix, rest = match.groups()
        depth = len(prefix) // 4
        name = rest.strip()
        if any(c in name for c in "{}*+") or " " in name:
            continue
        stack = stack[:depth]
        stack.append(name.rstrip("/"))
        full = repo_root.joinpath(*stack)
        if not full.exists():
            missing.append((name, full))
    assert missing == [], f"ARCHITECTURE.md tree references missing paths: {missing}"


def test_architecture_md_node_types_match_schema() -> None:
    """D13: ARCHITECTURE.md's node-type list is a superset of schema exports.

    If the schema adds a new node class, the architecture doc must document it.
    Node-type entries are `**\\`TypeName\\`**` in the `## Node types` section.
    Compared against every `BaseNode` subclass exported from `afls.schema`.
    """
    repo_root = Path(__file__).resolve().parents[2]
    arch_md = repo_root / "directives-ai" / "ARCHITECTURE.md"
    text = arch_md.read_text(encoding="utf-8")

    entry_re = re.compile(r"\*\*`([A-Z][A-Za-z0-9]+)`\*\*")
    documented = set(entry_re.findall(text))

    schema_node_types: set[str] = set()
    for name in afls_schema.__all__:
        obj = getattr(afls_schema, name)
        if not inspect.isclass(obj):
            continue
        if not issubclass(obj, BaseNode):
            continue
        if obj is BaseNode:
            continue
        schema_node_types.add(name)

    missing = schema_node_types - documented
    assert missing == set(), (
        f"Node types exported by schema but undocumented in ARCHITECTURE.md: {missing}"
    )
