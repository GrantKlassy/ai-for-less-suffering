# engine/ --- the typed reasoning core

Python 3.12+, Pydantic-first. The engine is the authoritative validator and reasoner for `../data/`. The frontend trusts it and never re-validates.

## Layout

- `afls/cli.py` --- Typer CLI. Entry point: `afls` (see `pyproject.toml` scripts).
- `afls/schema/` --- one file per node kind. `base.py` sets `extra="forbid"` on every model.
- `afls/storage/` --- YAML read/write with round-trip preservation.
- `afls/queries/` --- read-only graph lookups.
- `afls/reasoning/` --- Claude-powered steelman and analysis generators. Writes to `../public-output/analyses/`.
- `afls/config.py`, `afls/output.py` --- env/config and rich-console output.
- `tests/` --- pytest. `test_layering.py` is a cross-layer invariant, not a schema test.

## Running

- `task engine:install` --- `uv sync` inside `engine/`.
- `task engine:test` --- pytest.
- `task engine:check` --- ruff + mypy (strict).
- `task engine:cli -- <args>` --- invoke `afls` CLI, e.g. `task engine:cli -- validate`.

## Discipline

- Every behavior change needs a test. Tests live under `tests/`, one module per subject.
- mypy is strict (`disallow_untyped_defs`, `disallow_any_unimported`). New code needs complete annotations.
- `extra="forbid"` on `BaseNode` is load-bearing --- do not relax it. It is how the presentation/data boundary stays honest.
- Referential integrity (does every `NodeRef` resolve?) is checked in `afls validate`. If you add a new ref field to any schema, update the validator's traversal in `cli.py`.

## Reasoning pipeline

`steelman` (and siblings under `afls/reasoning/`) build structured prompts from the graph, call Claude, validate the response against a Pydantic analysis schema, and emit JSON+markdown pairs to `../public-output/analyses/`. The frontend loads those JSON files at build time via `../src/lib/analysis.ts`; no Python runs at site build.

## What doesn't belong here

Presentation concerns. HTML, emojis, colors, Astro components --- all in `../src/`. The engine is pure-data-and-reasoning; if you find yourself adding a display-related field, you're in the wrong layer.
