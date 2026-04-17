"""afls CLI entrypoint. Commands are registered here; storage and schema do the work."""

from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from afls import __version__
from afls.config import data_dir, db_path, public_output_dir
from afls.output import (
    analysis_paths,
    leverage_analysis_paths,
    write_analysis_json,
    write_analysis_markdown,
    write_leverage_json,
    write_leverage_markdown,
)
from afls.queries.leverage import run_leverage_query
from afls.queries.palantir import run_palantir_query
from afls.reasoning import AnthropicClient
from afls.schema import (
    BaseNode,
    BlindSpot,
    Bridge,
    Camp,
    Convergence,
    DescriptiveClaim,
    Intervention,
    MethodTag,
    Support,
    Warrant,
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

_SLUG_KINDS = {"camp", "friction_layer"}
_ID_PREFIX: dict[str, str] = {
    "descriptive_claim": "desc",
    "normative_claim": "norm",
    "camp": "camp",
    "intervention": "intv",
    "friction_layer": "friction",
    "bridge": "bridge",
    "convergence": "conv",
    "blindspot": "blind",
    "source": "src",
    "warrant": "war",
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
        for ref in camp.disputed_warrants:
            expect(camp.id, "disputed_warrants", ref, "warrant")
    for intv in list_nodes(Intervention, root):
        for ref in intv.friction_scores:
            expect(intv.id, "friction_scores", ref, "friction_layer")
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
    warrants = list_nodes(Warrant, root)
    for warrant in warrants:
        expect(warrant.id, "claim_id", warrant.claim_id, "descriptive_claim")
        expect(warrant.id, "source_id", warrant.source_id, "source")

    if errors:
        for err in errors:
            typer.secho(f"  {err}", fg="red")
        typer.secho(
            f"\n{len(errors)} errors across {len(id_to_kind)} nodes",
            fg="red",
            bold=True,
        )
        raise typer.Exit(1)

    warnings = _confidence_lint(list_nodes(DescriptiveClaim, root), warrants)
    for warn in warnings:
        typer.secho(f"  warn: {warn}", fg="yellow")
    suffix = f", {len(warnings)} warnings" if warnings else ""
    typer.secho(
        f"ok: {len(id_to_kind)} nodes, no referential errors{suffix}", fg="green"
    )


def _confidence_lint(
    claims: list[DescriptiveClaim], warrants: list[Warrant]
) -> list[str]:
    """Operator-discipline warnings on claim confidence vs. attached warrants."""
    by_claim: dict[str, list[Warrant]] = {}
    for warrant in warrants:
        by_claim.setdefault(warrant.claim_id, []).append(warrant)
    messages: list[str] = []
    for claim in claims:
        supporting = [
            w for w in by_claim.get(claim.id, []) if w.supports is Support.SUPPORT
        ]
        if claim.confidence > 0.5 and not supporting:
            messages.append(
                f"{claim.id}: confidence {claim.confidence} with no supporting warrants"
            )
        if (
            claim.confidence > 0.8
            and supporting
            and all(w.method_tag is MethodTag.EXPERT_ESTIMATE for w in supporting)
        ):
            messages.append(
                f"{claim.id}: confidence {claim.confidence} backed only by "
                "expert_estimate warrants"
            )
    return messages


@app.command()
def reindex() -> None:
    """Rebuild the SQLite index from YAML."""
    db = db_path()
    count = rebuild(data_dir(), db)
    typer.secho(f"indexed {count} nodes -> {db}", fg="green")


_SUPPORTED_QUERIES: tuple[str, ...] = ("palantir", "leverage")


@app.command()
def query(name: str) -> None:
    """Run a named reasoning query. Supported: `palantir`, `leverage`."""
    if name not in _SUPPORTED_QUERIES:
        typer.secho(
            f"unknown query {name!r}. supported: {', '.join(_SUPPORTED_QUERIES)}",
            fg="red",
        )
        raise typer.Exit(1)
    client = AnthropicClient()
    if name == "palantir":
        palantir_analysis = run_palantir_query(client, data_dir())
        json_path, md_path = analysis_paths(public_output_dir(), palantir_analysis)
        write_analysis_json(palantir_analysis, json_path)
        write_analysis_markdown(palantir_analysis, md_path, data_dir())
    else:
        leverage_analysis = run_leverage_query(client, data_dir())
        json_path, md_path = leverage_analysis_paths(
            public_output_dir(), leverage_analysis
        )
        write_leverage_json(leverage_analysis, json_path)
        write_leverage_markdown(leverage_analysis, md_path, data_dir())
    typer.secho(f"wrote {json_path}", fg="green")
    typer.secho(f"wrote {md_path}", fg="green")


if __name__ == "__main__":
    app()
