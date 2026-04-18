"""afls CLI entrypoint. Commands are registered here; storage and schema do the work."""

from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from afls import __version__
from afls.config import data_dir, db_path, public_output_dir, repo_root
from afls.ingest import fetch_and_extract
from afls.output import (
    analysis_paths,
    leverage_analysis_paths,
    steelman_analysis_paths,
    write_analysis_json,
    write_analysis_markdown,
    write_leverage_json,
    write_leverage_markdown,
    write_steelman_json,
    write_steelman_markdown,
)
from afls.queries.leverage import run_leverage_query
from afls.queries.palantir import run_palantir_query
from afls.queries.steelman import run_steelman_query
from afls.reasoning import AnthropicClient, ReasoningError, run_ingest_query
from afls.schema import (
    BaseNode,
    BlindSpot,
    Bridge,
    Camp,
    Convergence,
    DescriptiveClaim,
    Evidence,
    Intervention,
    MethodTag,
    Provenance,
    Source,
    Support,
    new_id,
    slug_id,
)
from afls.storage import (
    NODE_TYPES,
    list_nodes,
    load_node,
    rebuild,
    save_node,
)

app = typer.Typer(
    name="afls",
    help="Typed reasoning engine for AI-toward-suffering-reduction.",
    no_args_is_help=True,
)
console = Console()

_SLUG_KINDS = {"camp", "friction_layer", "harm_layer", "suffering_layer"}
_ID_PREFIX: dict[str, str] = {
    "descriptive_claim": "desc",
    "normative_claim": "norm",
    "camp": "camp",
    "intervention": "intv",
    "friction_layer": "friction",
    "harm_layer": "harm",
    "suffering_layer": "suffering",
    "bridge": "bridge",
    "convergence": "conv",
    "blindspot": "blind",
    "source": "src",
    "evidence": "evi",
}


@app.callback()
def _root() -> None:
    """Root callback forces Typer into subcommand mode."""


@app.command()
def version() -> None:
    """Print the afls version."""
    typer.echo(f"afls {__version__}")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        typer.secho(f"file not found: {path}", fg="red")
        raise typer.Exit(1)
    with path.open() as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        typer.secho(f"expected a YAML mapping at top level of {path}", fg="red")
        raise typer.Exit(1)
    return data


def _default_id(data: dict[str, Any], kind: str) -> str:
    prefix = _ID_PREFIX[kind]
    if kind in _SLUG_KINDS:
        name = data.get("name")
        if not name:
            typer.secho(
                f"{kind} requires a `name` field to derive an id (or pre-set `id`)",
                fg="red",
            )
            raise typer.Exit(1)
        return slug_id(prefix, str(name))
    return new_id(prefix)


def _validate_or_exit[T: BaseNode](model: type[T], data: dict[str, Any]) -> T:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        typer.secho(f"validation failed for {model.__name__}:", fg="red", bold=True)
        typer.echo(str(exc))
        raise typer.Exit(1) from exc


@app.command()
def add(from_file: Path) -> None:
    """Add a node from a YAML fragment. `kind` is required; `id` is auto-generated if absent."""
    data = _load_yaml(from_file)
    kind = data.get("kind")
    if not isinstance(kind, str) or kind not in NODE_TYPES:
        typer.secho(
            f"top-level `kind` missing or unknown: {kind!r}. "
            f"valid: {sorted(NODE_TYPES)}",
            fg="red",
        )
        raise typer.Exit(1)
    if "id" not in data:
        data["id"] = _default_id(data, kind)
    if kind == "source" and not data.get("accessed_at"):
        data["accessed_at"] = date.today().isoformat()
    model = NODE_TYPES[kind]
    node = _validate_or_exit(model, data)
    path = save_node(node, data_dir())
    typer.secho(f"saved {node.id} -> {path}", fg="green")


def _summary(node: BaseNode) -> str:
    text = getattr(node, "text", None) or getattr(node, "name", None) or ""
    return str(text)[:80]


@app.command("list")
def list_cmd(kind: str) -> None:
    """List every node of a given kind (sorted by id)."""
    if kind not in NODE_TYPES:
        typer.secho(f"unknown kind {kind!r}. valid: {sorted(NODE_TYPES)}", fg="red")
        raise typer.Exit(1)
    model = NODE_TYPES[kind]
    nodes = list_nodes(model, data_dir())
    if not nodes:
        typer.echo(f"no {kind} nodes")
        return
    table = Table(title=f"{kind} ({len(nodes)})")
    table.add_column("id", style="cyan")
    table.add_column("summary")
    for node in nodes:
        table.add_row(node.id, _summary(node))
    console.print(table)


def _find_node_by_id(node_id: str) -> BaseNode | None:
    """Walk YAML directories to locate a node by id across every kind."""
    for model in NODE_TYPES.values():
        try:
            return load_node(model, node_id, data_dir())
        except FileNotFoundError:
            continue
    return None


def _dump_yaml(node: BaseNode) -> str:
    return yaml.safe_dump(
        node.model_dump(mode="json"), sort_keys=True, default_flow_style=False
    )


@app.command()
def show(node_id: str) -> None:
    """Dump a node's YAML to stdout."""
    node = _find_node_by_id(node_id)
    if node is None:
        typer.secho(f"no node with id {node_id!r}", fg="red")
        raise typer.Exit(1)
    typer.echo(_dump_yaml(node).rstrip())


@app.command()
def edit(node_id: str) -> None:
    """Open a node's YAML in $EDITOR (default: vi), re-validate, save."""
    node = _find_node_by_id(node_id)
    if node is None:
        typer.secho(f"no node with id {node_id!r}", fg="red")
        raise typer.Exit(1)
    editor = os.environ.get("EDITOR", "vi")
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
        tmp.write(_dump_yaml(node))
        tmp_path = Path(tmp.name)
    try:
        subprocess.run([editor, str(tmp_path)], check=True)
        with tmp_path.open() as handle:
            edited_data = yaml.safe_load(handle)
        if not isinstance(edited_data, dict):
            typer.secho("edited YAML must be a mapping", fg="red")
            raise typer.Exit(1)
        edited_data["updated_at"] = datetime.now(UTC).isoformat()
        model = type(node)
        edited = _validate_or_exit(model, edited_data)
        if edited.id != node.id:
            typer.secho(
                f"id is immutable ({node.id!r} -> {edited.id!r}); aborting",
                fg="red",
            )
            raise typer.Exit(1)
        if edited.kind != node.kind:
            typer.secho(
                f"kind is immutable ({node.kind!r} -> {edited.kind!r}); aborting",
                fg="red",
            )
            raise typer.Exit(1)
        save_node(edited, data_dir())
        typer.secho(f"saved {edited.id}", fg="green")
    finally:
        tmp_path.unlink(missing_ok=True)


@app.command()
def validate() -> None:
    """Check referential integrity across every NodeRef field."""
    root = data_dir()
    id_to_kind: dict[str, str] = {}
    for kind, model in NODE_TYPES.items():
        for node in list_nodes(model, root):
            id_to_kind[node.id] = kind
    errors: list[str] = []

    def expect(owner: str, field: str, ref: str, expected: str) -> None:
        found = id_to_kind.get(ref)
        if found is None:
            errors.append(f"{owner}.{field}: unknown id {ref!r}")
        elif found != expected:
            errors.append(f"{owner}.{field}: {ref!r} is {found}, expected {expected}")

    for camp in list_nodes(Camp, root):
        for ref in camp.held_descriptive:
            expect(camp.id, "held_descriptive", ref, "descriptive_claim")
        for ref in camp.held_normative:
            expect(camp.id, "held_normative", ref, "normative_claim")
        for ref in camp.disputed_evidence:
            expect(camp.id, "disputed_evidence", ref, "evidence")
    for intv in list_nodes(Intervention, root):
        for ref in intv.friction_scores:
            expect(intv.id, "friction_scores", ref, "friction_layer")
        for ref in intv.harm_scores:
            expect(intv.id, "harm_scores", ref, "harm_layer")
        for ref in intv.suffering_reduction_scores:
            expect(intv.id, "suffering_reduction_scores", ref, "suffering_layer")
    for bridge in list_nodes(Bridge, root):
        expect(bridge.id, "from_camp", bridge.from_camp, "camp")
        expect(bridge.id, "to_camp", bridge.to_camp, "camp")
    for conv in list_nodes(Convergence, root):
        expect(conv.id, "intervention_id", conv.intervention_id, "intervention")
        for ref in conv.camps:
            expect(conv.id, "camps", ref, "camp")
        for camp_id, norm_id in conv.divergent_reasons.items():
            expect(conv.id, "divergent_reasons.key", camp_id, "camp")
            expect(conv.id, "divergent_reasons.value", norm_id, "normative_claim")
    for blindspot in list_nodes(BlindSpot, root):
        expect(blindspot.id, "flagged_camp_id", blindspot.flagged_camp_id, "camp")
    evidence_list = list_nodes(Evidence, root)
    for evidence in evidence_list:
        expect(evidence.id, "claim_id", evidence.claim_id, "descriptive_claim")
        expect(evidence.id, "source_id", evidence.source_id, "source")

    if errors:
        for err in errors:
            typer.secho(f"  {err}", fg="red")
        typer.secho(
            f"\n{len(errors)} errors across {len(id_to_kind)} nodes",
            fg="red",
            bold=True,
        )
        raise typer.Exit(1)

    warnings = _confidence_lint(list_nodes(DescriptiveClaim, root), evidence_list)
    for warn in warnings:
        typer.secho(f"  warn: {warn}", fg="yellow")
    suffix = f", {len(warnings)} warnings" if warnings else ""
    typer.secho(
        f"ok: {len(id_to_kind)} nodes, no referential errors{suffix}", fg="green"
    )


def _confidence_lint(
    claims: list[DescriptiveClaim], evidence_list: list[Evidence]
) -> list[str]:
    """Operator-discipline warnings on claim confidence vs. attached evidence."""
    by_claim: dict[str, list[Evidence]] = {}
    for evidence in evidence_list:
        by_claim.setdefault(evidence.claim_id, []).append(evidence)
    messages: list[str] = []
    for claim in claims:
        supporting = [
            e for e in by_claim.get(claim.id, []) if e.supports is Support.SUPPORT
        ]
        if claim.confidence > 0.5 and not supporting:
            messages.append(
                f"{claim.id}: confidence {claim.confidence} with no supporting evidence"
            )
        if (
            claim.confidence > 0.8
            and supporting
            and all(e.method_tag is MethodTag.EXPERT_ESTIMATE for e in supporting)
        ):
            messages.append(
                f"{claim.id}: confidence {claim.confidence} backed only by "
                "expert_estimate evidence"
            )
    return messages


@app.command()
def reindex() -> None:
    """Rebuild the SQLite index from YAML."""
    db = db_path()
    count = rebuild(data_dir(), db)
    typer.secho(f"indexed {count} nodes -> {db}", fg="green")


_SUPPORTED_QUERIES: tuple[str, ...] = ("palantir", "leverage", "steelman")


@app.command()
def query(
    name: str,
    target: str = typer.Option(
        "",
        "--target",
        help="Intervention id to target. Required for `steelman`.",
    ),
) -> None:
    """Run a named reasoning query. Supported: `palantir`, `leverage`, `steelman`."""
    if name not in _SUPPORTED_QUERIES:
        typer.secho(
            f"unknown query {name!r}. supported: {', '.join(_SUPPORTED_QUERIES)}",
            fg="red",
        )
        raise typer.Exit(1)
    if name == "steelman" and not target:
        typer.secho("steelman requires --target <intervention_id>", fg="red")
        raise typer.Exit(1)
    client = AnthropicClient()
    if name == "palantir":
        palantir_analysis = run_palantir_query(client, data_dir())
        json_path, md_path = analysis_paths(public_output_dir(), palantir_analysis)
        write_analysis_json(palantir_analysis, json_path)
        write_analysis_markdown(palantir_analysis, md_path, data_dir())
    elif name == "leverage":
        leverage_analysis = run_leverage_query(client, data_dir())
        json_path, md_path = leverage_analysis_paths(
            public_output_dir(), leverage_analysis
        )
        write_leverage_json(leverage_analysis, json_path)
        write_leverage_markdown(leverage_analysis, md_path, data_dir())
    else:
        steelman_analysis = run_steelman_query(
            client, data_dir(), target_intervention_id=target
        )
        json_path, md_path = steelman_analysis_paths(
            public_output_dir(), steelman_analysis
        )
        write_steelman_json(steelman_analysis, json_path)
        write_steelman_markdown(steelman_analysis, md_path, data_dir())
    typer.secho(f"wrote {json_path}", fg="green")
    typer.secho(f"wrote {md_path}", fg="green")


_INGEST_TOOL: str = f"afls-ingest/{__version__}"


def _git_sha() -> str:
    """Return HEAD SHA for provenance. Falls back to 'unknown' outside a git tree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_root(),
        )
    except (subprocess.CalledProcessError, FileNotFoundError, RuntimeError):
        return "unknown"
    return result.stdout.strip() or "unknown"


_fetch_for_ingest = fetch_and_extract
"""Module-level fetch hook. Tests monkeypatch this to avoid the network."""


def _build_ingest_client() -> AnthropicClient:
    """Module-level client factory. Tests monkeypatch this to inject a fake SDK."""
    return AnthropicClient()


@app.command()
def ingest(url: str) -> None:
    """Fetch a URL and draft Source + DescriptiveClaims + Evidence YAML via Claude."""
    typer.secho(f"fetching {url}", fg="cyan")
    try:
        final_url, article_text, sha256 = _fetch_for_ingest(url)
    except Exception as exc:
        typer.secho(f"fetch failed: {exc}", fg="red")
        raise typer.Exit(1) from exc
    if not article_text.strip():
        typer.secho("fetched page contained no extractable text", fg="red")
        raise typer.Exit(1)
    typer.secho(
        f"extracted {len(article_text)} chars (sha256={sha256[:12]}...) from {final_url}",
        fg="cyan",
    )

    typer.secho("drafting source+claims+evidence (opus)...", fg="cyan")
    client = _build_ingest_client()
    try:
        draft = run_ingest_query(
            client, data_dir(), url=final_url, article_text=article_text
        )
    except ReasoningError as exc:
        typer.secho(f"LLM draft failed: {exc}", fg="red")
        raise typer.Exit(1) from exc

    source_id = f"{_ID_PREFIX['source']}_{draft.source.id_slug}"
    if _find_node_by_id(source_id) is not None:
        typer.secho(
            f"collision: source {source_id!r} already exists; rename id_slug and retry",
            fg="red",
        )
        raise typer.Exit(1)

    claim_ids: list[str] = []
    seen_slugs: set[str] = set()
    for claim_draft in draft.claims:
        if claim_draft.id_slug in seen_slugs:
            typer.secho(
                f"collision: LLM proposed duplicate claim id_slug {claim_draft.id_slug!r}",
                fg="red",
            )
            raise typer.Exit(1)
        seen_slugs.add(claim_draft.id_slug)
        candidate = f"{_ID_PREFIX['descriptive_claim']}_{claim_draft.id_slug}"
        if _find_node_by_id(candidate) is not None:
            typer.secho(
                f"collision: descriptive claim {candidate!r} already exists; "
                "rename id_slug and retry",
                fg="red",
            )
            raise typer.Exit(1)
        claim_ids.append(candidate)

    for ev_draft in draft.evidence:
        if ev_draft.claim_idx >= len(draft.claims):
            typer.secho(
                f"LLM drafted evidence with claim_idx={ev_draft.claim_idx} "
                f"but only {len(draft.claims)} claims were returned",
                fg="red",
            )
            raise typer.Exit(1)

    provenance = Provenance(
        method="httpx",
        tool=_INGEST_TOOL,
        git_sha=_git_sha(),
        at=datetime.now(UTC),
        raw_content_hash=sha256,
    )
    source = Source(
        id=source_id,
        source_kind=draft.source.source_kind,
        title=draft.source.title,
        url=final_url,
        authors=list(draft.source.authors),
        published_at=draft.source.published_at,
        accessed_at=date.today().isoformat(),
        reliability=draft.source.reliability,
        notes=draft.source.notes,
        provenance=provenance,
    )
    source_path = save_node(source, data_dir())
    typer.secho(f"  wrote {source_path}", fg="green")

    claims: list[DescriptiveClaim] = []
    for claim_draft, claim_id in zip(draft.claims, claim_ids, strict=True):
        claim = DescriptiveClaim(
            id=claim_id,
            text=claim_draft.text,
            confidence=claim_draft.confidence,
        )
        claim_path = save_node(claim, data_dir())
        claims.append(claim)
        typer.secho(f"  wrote {claim_path}", fg="green")

    for ev_draft in draft.evidence:
        claim = claims[ev_draft.claim_idx]
        evidence = Evidence(
            id=new_id(_ID_PREFIX["evidence"]),
            claim_id=claim.id,
            source_id=source.id,
            locator=ev_draft.locator,
            quote=ev_draft.quote,
            method_tag=ev_draft.method_tag,
            supports=ev_draft.supports,
            weight=ev_draft.weight,
        )
        ev_path = save_node(evidence, data_dir())
        typer.secho(f"  wrote {ev_path}", fg="green")

    typer.secho(
        f"\ningested: 1 source, {len(claims)} claims, {len(draft.evidence)} evidence edges",
        fg="green",
        bold=True,
    )
    typer.secho(
        f"review with: afls edit {source.id}  (then the desc_* / evi_* nodes)",
        fg="cyan",
    )


if __name__ == "__main__":
    app()
