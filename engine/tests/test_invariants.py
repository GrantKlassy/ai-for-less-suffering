"""Invariant tests over the live corpus + shared infrastructure.

Linkage (test_linkage.py) proved every ref resolves. Schema drift
(test_schema_drift.py) proved both sides share the same enums/prefixes.
These assert the orthogonal invariants --- node-hygiene, field-range, output
hygiene --- that don't fit either category but are worth catching in CI.

Every test here targets the actual committed data, not synthetic fixtures.
A failure means a YAML file that validates in isolation nevertheless breaks
a cross-file or cross-layer assumption.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from afls.cli import _ID_PREFIX
from afls.config import data_dir, public_output_dir, repo_root
from afls.schema import (
    BaseNode,
    Camp,
    Convergence,
    DescriptiveClaim,
    Evidence,
    Source,
)
from afls.storage import NODE_SUBDIRS, NODE_TYPES, list_nodes

# ---------------------------------------------------------------------------
# E1: storage reads are confined to data/.
# ---------------------------------------------------------------------------


def test_e1_list_nodes_reads_only_under_data_dir(tmp_path: Path) -> None:
    """`list_nodes` walks NODE_SUBDIRS relative to the root it's given. Prove
    it never escapes via a traversal (`..`) or symlink --- if a subdir entry
    ever grows a relative-parent segment, data/ could leak arbitrary disk.
    """
    for model, subdir in NODE_SUBDIRS.items():
        assert ".." not in subdir, (
            f"NODE_SUBDIRS[{model.__name__}] contains '..' --- path would "
            f"escape the data root"
        )
        assert "/" not in "".join(subdir), (
            f"NODE_SUBDIRS[{model.__name__}] contains a '/' in a single "
            f"segment --- split it into multiple tuple elements instead"
        )
        # And the resolved path must stay inside tmp_path.
        resolved = tmp_path.joinpath(*subdir).resolve()
        assert resolved.is_relative_to(tmp_path.resolve()), (
            f"NODE_SUBDIRS[{model.__name__}] resolves outside the root"
        )


# ---------------------------------------------------------------------------
# E2: canary pair atomicity --- file presence + GPG verification.
# ---------------------------------------------------------------------------


def test_e2_canary_pair_is_present() -> None:
    """Both halves of the signed canary must be in the repo. A `*.txt` without
    a matching `*.asc` (or vice versa) is exactly what lefthook's pair-check
    is meant to reject; assert the committed tree satisfies that invariant.
    """
    canary = repo_root() / "public" / "canary.txt"
    sig = repo_root() / "public" / "canary.txt.asc"
    assert canary.exists(), "public/canary.txt is missing"
    assert sig.exists(), "public/canary.txt.asc is missing"
    # Empty files would pass the pair-check but make the GPG verify
    # meaningless --- guard against it explicitly.
    assert canary.stat().st_size > 0, "public/canary.txt is empty"
    assert sig.stat().st_size > 0, "public/canary.txt.asc is empty"


def test_e2_canary_signature_verifies() -> None:
    """Detached signature must verify against the committed canary text.

    Runs gpg in-process using the pubkey committed to the repo. The sig-check
    is the core invariant the lefthook pair-check gates on; a bit-flip in
    either file would break this.
    """
    gpg = subprocess.run(["which", "gpg"], capture_output=True, text=True)
    if gpg.returncode != 0:
        pytest.skip("gpg not installed; skipping signature verification")

    canary = repo_root() / "public" / "canary.txt"
    sig = repo_root() / "public" / "canary.txt.asc"
    pubkey = repo_root() / "public" / "canary-key.asc"
    assert pubkey.exists(), "public/canary-key.asc is missing"

    # Isolate into a throwaway gpg home so we don't pollute the user's keyring.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        env = {"GNUPGHOME": tmp}
        imp = subprocess.run(
            ["gpg", "--batch", "--import", str(pubkey)],
            capture_output=True,
            text=True,
            env=env,
        )
        assert imp.returncode == 0, f"gpg import failed: {imp.stderr}"
        verify = subprocess.run(
            ["gpg", "--batch", "--verify", str(sig), str(canary)],
            capture_output=True,
            text=True,
            env=env,
        )
        assert verify.returncode == 0, (
            f"canary signature does not verify: {verify.stderr}"
        )


# ---------------------------------------------------------------------------
# E3: every camp holds something.
# ---------------------------------------------------------------------------


def test_e3_every_camp_holds_at_least_one_claim() -> None:
    """A camp with no held_* refs is a name with no content --- it won't
    appear on the graph via any structural edge. The schema allows it for
    draft state; this test flags any that shipped empty."""
    offenders: list[str] = []
    for camp in list_nodes(Camp, data_dir()):
        if not camp.held_descriptive and not camp.held_normative:
            offenders.append(camp.id)
    assert not offenders, (
        f"camps with zero held_descriptive AND zero held_normative: "
        f"{offenders}"
    )


# ---------------------------------------------------------------------------
# E4: no orphan descriptive claims.
# ---------------------------------------------------------------------------


def test_e4_no_orphan_descriptive_claims() -> None:
    """A descriptive claim is an orphan if no camp holds it and no evidence
    cites it. An orphan is not wrong per se, but it's invisible on the graph
    --- worth flagging so it's either wired up or deliberately removed.
    """
    root = data_dir()
    held: set[str] = set()
    for camp in list_nodes(Camp, root):
        held.update(camp.held_descriptive)
    cited: set[str] = {e.claim_id for e in list_nodes(Evidence, root)}
    reachable = held | cited

    orphans = [
        c.id for c in list_nodes(DescriptiveClaim, root) if c.id not in reachable
    ]
    assert not orphans, (
        f"descriptive claims with zero incoming camp or evidence edges: {orphans}"
    )


# ---------------------------------------------------------------------------
# E5: every source has at least one evidence citation.
# ---------------------------------------------------------------------------


# Sources intentionally staged without evidence yet. Adding to this set is
# a deliberate act: "I'm parking this source for later extraction." The E5
# test catches unknown additions (a new source landed uncited without being
# listed here) and unknown removals (a source got wired up or deleted, time
# to trim the allowlist). Both directions are signal.
_KNOWN_UNCITED_SOURCES: frozenset[str] = frozenset(
    {
        "src_andreessen_techno_optimist",
        "src_eu_ai_act",
        "src_meta_llama_release",
        "src_nyt_v_openai_complaint",
        "src_openai_agi_plan",
        "src_semianalysis_datacenter",
        "src_vatican_rome_call",
    }
)


def test_e5_source_orphans_match_the_known_set() -> None:
    """A source with zero attached evidence has no incoming graph edges; the
    detail page still renders but the graph can't reach it. Per the plan,
    orphans are allowed if explicitly named. `_KNOWN_UNCITED_SOURCES` above
    is that list --- the test fails if the actual set drifts from it.
    """
    root = data_dir()
    cited: set[str] = {e.source_id for e in list_nodes(Evidence, root)}
    actual_orphans = frozenset(
        s.id for s in list_nodes(Source, root) if s.id not in cited
    )
    new_orphans = actual_orphans - _KNOWN_UNCITED_SOURCES
    resolved_orphans = _KNOWN_UNCITED_SOURCES - actual_orphans
    assert not new_orphans, (
        f"new uncited source(s) without allowlist entry: {sorted(new_orphans)}. "
        f"Either add evidence or extend _KNOWN_UNCITED_SOURCES."
    )
    assert not resolved_orphans, (
        f"source(s) listed in _KNOWN_UNCITED_SOURCES are now cited or deleted: "
        f"{sorted(resolved_orphans)}. Remove them from the allowlist."
    )


# ---------------------------------------------------------------------------
# E6: every id uses a known prefix.
# ---------------------------------------------------------------------------


def test_e6_all_ids_use_a_known_prefix() -> None:
    """Every YAML file's id must start with a prefix registered in _ID_PREFIX.
    The CLI's `add` command generates correct prefixes, but a hand-edited
    file could sneak through with a wrong one; the TS prefix-dispatcher would
    then return null and links would 404.
    """
    root = data_dir()
    known_prefixes = {f"{prefix}_" for prefix in _ID_PREFIX.values()}
    offenders: list[tuple[str, str]] = []
    for kind, model in NODE_TYPES.items():
        for node in list_nodes(model, root):
            if not any(node.id.startswith(p) for p in known_prefixes):
                offenders.append((kind, node.id))
    assert not offenders, (
        f"nodes whose id does not start with any known prefix in _ID_PREFIX: "
        f"{offenders}"
    )


# ---------------------------------------------------------------------------
# E7: no YAML carries a presentation field.
# ---------------------------------------------------------------------------

_PRESENTATION_FIELDS: tuple[str, ...] = ("emoji", "color", "icon", "classes")


def test_e7_no_presentation_fields_in_any_yaml() -> None:
    """Pydantic extra='forbid' catches this at load time, but a clean grep
    gives a better error message: 'presentation belongs in src/, not data/'
    instead of 'Extra inputs are not permitted'. Extends the existing check
    in test_layering.py from camps-only to the whole data/ tree.
    """
    root = data_dir()
    offenders: list[tuple[str, str]] = []
    for yaml_file in root.rglob("*.yaml"):
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            continue
        for field in _PRESENTATION_FIELDS:
            if field in data:
                offenders.append((str(yaml_file.relative_to(root)), field))
    assert not offenders, (
        f"YAML carries presentation fields (belong in src/lib/*): {offenders}"
    )


# ---------------------------------------------------------------------------
# E8: every [0,1] field in real data holds its range.
# ---------------------------------------------------------------------------


def _walk_numeric(
    obj: object, path: str = ""
) -> list[tuple[str, float]]:
    """Flatten a model_dump dict into (path, float) pairs for numeric values."""
    results: list[tuple[str, float]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            sub_path = f"{path}.{key}" if path else str(key)
            results.extend(_walk_numeric(value, sub_path))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            results.extend(_walk_numeric(value, f"{path}[{i}]"))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        results.append((path, float(obj)))
    return results


# Numeric fields the schemas bound to [0, 1]. Any field NOT on this list is
# allowed to exceed 1 (e.g. id counts, arbitrary weights). Kept explicit so
# a new in-range field can't land without a test update.
_BOUNDED_FIELDS: frozenset[str] = frozenset(
    {
        "confidence",
        "reliability",
        "weight",
        "leverage_score",
    }
)

# Score dicts whose values are bounded to [0, 1].
_BOUNDED_SCORE_CONTAINERS: frozenset[str] = frozenset(
    {
        "friction_scores",
        "harm_scores",
        "suffering_reduction_scores",
    }
)


def test_e8_bounded_fields_stay_in_range() -> None:
    """Pydantic Field(ge=0, le=1) is the structural guarantee --- this test
    is the redundant check against live data. If it ever fires, a schema
    relaxed its bound and no one caught it.
    """
    root = data_dir()
    offenders: list[tuple[str, str, float]] = []

    def check(node: BaseNode) -> None:
        dump = node.model_dump(mode="python")
        for path_segment, value in _walk_numeric(dump):
            in_range = 0.0 <= value <= 1.0
            if in_range:
                continue
            # Direct bounded fields --- `confidence`, `reliability`, etc.
            last = path_segment.rsplit(".", 1)[-1].split("[", 1)[0]
            if last in _BOUNDED_FIELDS:
                offenders.append((node.id, path_segment, value))
                continue
            # Bounded score containers --- dict-valued, range-checked per value.
            for container in _BOUNDED_SCORE_CONTAINERS:
                if f"{container}." in path_segment:
                    offenders.append((node.id, path_segment, value))
                    break

    for model in NODE_TYPES.values():
        for node in list_nodes(model, root):
            check(node)

    assert not offenders, (
        f"bounded field(s) outside [0,1]: {offenders}"
    )


# ---------------------------------------------------------------------------
# E9: every convergence has ≥2 distinct camps.
# ---------------------------------------------------------------------------


def test_e9_convergences_link_at_least_two_distinct_camps() -> None:
    """Convergence is meaningful only when it spans ≥2 camps arriving at the
    same intervention. The schema declares `camps: list[NodeRef]` but does
    not enforce min-length or distinctness; this asserts it at corpus level.
    """
    root = data_dir()
    offenders: list[tuple[str, int, int]] = []
    for conv in list_nodes(Convergence, root):
        unique = len(set(conv.camps))
        if len(conv.camps) < 2 or unique < 2:
            offenders.append((conv.id, len(conv.camps), unique))
    assert not offenders, (
        f"convergences with fewer than 2 distinct camps "
        f"(id, total, unique): {offenders}"
    )


# ---------------------------------------------------------------------------
# E10: analyses are Claude-contamination-free.
# ---------------------------------------------------------------------------


def test_e10_no_co_authored_by_in_analyses() -> None:
    """Grant's standing rule: no Co-Authored-By trailer on anything under his
    real-name account. Analyses are LLM-authored; if a prompt ever starts
    surfacing the trailer, it would ship to production via static JSON.
    """
    analyses_dir = public_output_dir() / "analyses"
    if not analyses_dir.exists():
        pytest.skip("no analyses directory; nothing to check")

    # Check JSON files. We also check .md for thoroughness, since analyses
    # ship as JSON+markdown pairs.
    contaminated: list[tuple[str, str]] = []
    needle = "Co-Authored-By"
    for path in analyses_dir.iterdir():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if needle in text:
            contaminated.append((path.name, needle))
    assert not contaminated, (
        f"analyses contain Co-Authored-By trailer: {contaminated}"
    )


def test_e10_json_analyses_parse_cleanly() -> None:
    """Cheap additional guard: every analysis JSON is valid JSON. If an
    analysis shipped with a truncated / malformed file, the site build would
    produce an empty detail page without failing; catch it here instead.
    """
    analyses_dir = public_output_dir() / "analyses"
    if not analyses_dir.exists():
        pytest.skip("no analyses directory")
    malformed: list[tuple[str, str]] = []
    for path in analyses_dir.glob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            malformed.append((path.name, str(exc)))
    assert not malformed, f"malformed analysis JSON: {malformed}"
