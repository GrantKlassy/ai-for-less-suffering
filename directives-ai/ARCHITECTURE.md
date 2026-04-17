# architecture

This is the durable spec for the tool MANIFESTO.md asks for. Read it in the loop alongside BRAIN/MANIFESTO/CLAUDE.md.

## What this is

A local-first typed reasoning engine over a graph of descriptive claims, normative claims, camps, interventions, and the relations between them. Operator curates the graph and runs queries. The Claude API reasons over the graph; the validator rejects any output that smuggles values into facts. Shaped outputs ship publicly through the existing Astro site.

Not a website about reasoning. A reasoning tool that ships a website.

## Scope (settled)

- **Personal thinking tool, public output.** Single operator (Grant). No auth, no multi-user data, no account state. Shaped artifacts become public pages; the graph and operator priors stay local.
- **Symbolic + grounded ingest, both from day one.** CLI-driven curation for symbolic nodes; scheduled fetchers for grounded nodes (Epoch AI, SemiAnalysis, SEC filings, hiring signals). Grounded claims propose, never override.
- **Typed schema, not discipline.** The descriptive/normative separation is enforced by the validator, not trusted to the author. An LLM pass that produces a `DescriptiveClaim` without provenance or tags a `NormativeClaim` without an axiom family fails validation and retries.

## Language and runtime

Python 3.12+ for the engine. Pydantic 2 for schema. `uv` for deps. Anthropic Python SDK for reasoning (Opus 4.7 for reasoning passes, Haiku 4.5 for parsing/scaffolding). Ruff + mypy strict. pytest.

TypeScript/Astro site unchanged except for a new `analyses/` route that reads engine output from `public-output/` at build time.

## Repo layout

```
ai-for-less-suffering/
├── directives-ai/
│   ├── BRAIN.md
│   ├── MANIFESTO.md
│   ├── CLAUDE.md
│   └── ARCHITECTURE.md          # this file
├── engine/                       # Python reasoning engine
│   ├── pyproject.toml
│   ├── afls/
│   │   ├── schema/              # Pydantic models
│   │   ├── storage/             # SQLite + YAML canonical
│   │   ├── reasoning/           # Anthropic client + validator + prompts
│   │   ├── ingest/              # symbolic (CLI) + grounded (fetchers/)
│   │   ├── queries/             # palantir + reallocation + camp + leverage
│   │   ├── output/              # canonical JSON + shaped prose
│   │   └── cli.py               # typer entrypoint
│   └── tests/
├── data/                         # canonical typed graph (YAML, git-tracked)
│   ├── camps/
│   ├── claims/ {descriptive/, normative/}
│   ├── interventions/
│   ├── friction_layers/
│   ├── bridges/
│   ├── convergences/
│   ├── blindspots/
│   └── priors/grant.yaml        # BRAIN.md encoded as an operator prior set
├── public-output/                # engine-written shaped artifacts for Astro
│   └── analyses/*.json + *.md
└── src/ + Astro scaffolding      # existing
```

**Canonicality:** YAML files under `data/` are the source of truth --- diffable, git-friendly, sovereign. `data/afls.db` is a regenerable SQLite index (gitignored). `afls reindex` rebuilds it from YAML.

## Node types

All lifted from MANIFESTO.md. Nothing imported from external ontology.

- **`DescriptiveClaim`** --- factual assertion about the world. Fields: `text`, `sources[]`, `confidence: float ∈ [0,1]`, `evidence[]`, optional `provenance_url`.
- **`NormativeClaim`** --- value statement. Fields: `text`, `axiom_family` (Kantian / Capabilities / Theological / Consequentialist / e/acc / 80K-EA / poker-EV / Other), `axiom_detail`.
- **`Camp`** --- cluster of agents characterized by held nodes. Fields: `name`, `agents[]`, `held_descriptive: [ClaimRef]`, `held_normative: [ClaimRef]`. Examples: Palantir, Anthropic, x-risk, displaced workers, religious communities, accelerationists, environmentalists.
- **`Intervention`** --- proposed action. Fields: `text`, `kind: {technical, political, economic}`, `cost_estimate`, `leverage_score`, `friction_scores: {FrictionLayerId → float}`.
- **`FrictionLayer`** --- seeded with grid, capex, regulation, enterprise-absorption, public-backlash (from MANIFESTO).
- **`Bridge`** --- normative translation. Fields: `from_camp`, `to_camp`, `translation`, `caveats[]`. Lets camp A's position be reframed in camp B's language without false equivalence.
- **`Convergence`** --- first-class relation. Fields: `intervention_id`, `camps[]`, `divergent_reasons: {CampId → NormativeClaimId}`. Coalition logic as data: camps X and Y agree on intervention Z for _different normative reasons_.
- **`BlindSpot`** --- tool-generated flag. Fields: `against_prior_set`, `flagged_camp_id`, `reasoning`. Cross-references operator priors against the camp graph; surfaces under-weighted positions.

Every node carries `id` (content-addressed short hash), `created_at`, `updated_at`, and strict `extra="forbid"` validation.

## Reasoning layer

- **Client** (`engine/afls/reasoning/client.py`) --- wraps Anthropic SDK. Opus 4.7 for reasoning, Haiku 4.5 for parsing. Prompt caching markers on: schema JSON, camp registry, node-list slices. Long-lived context cached; query-specific context uncached.
- **Validator** (`engine/afls/reasoning/validator.py`) --- LLM outputs requested in JSON mode, parsed through Pydantic. On `ValidationError`: one retry with error context prepended to the prompt. Persistent fail raises to the operator --- no silent fallback, no default-filled nodes.
- **Prompts** (`engine/afls/reasoning/prompts.py`) --- system prompts per query. Loads BRAIN.md + MANIFESTO.md as operator context. Enforces directives-ai voice rules (no hedging, no manifesto voice, no EA-discourse smuggling).

## Ingest

Two modes, both first-class:

- **Symbolic** --- CLI. `afls add claim`, `add camp`, `add intervention`, etc. Operator curates.
- **Grounded** --- scheduled fetchers under `engine/afls/ingest/fetchers/`. Each fetcher emits proposed nodes with `provenance_url` + timestamp + source-reliability-adjusted confidence. Grounded claims _propose_; operator review (`afls ingest review`) promotes them to canonical.

## Queries

Each query is a module under `engine/afls/queries/` composing reasoning passes over the graph. Output: canonical JSON + a shaped prose companion markdown.

- **`palantir`** --- canonical test case and design anchor. Where Grant and Palantir converge descriptively, what bridges make cooperation on convergent infrastructure possible, where they diverge cleanly. Must produce at least one `Convergence`, one `Bridge`, one `BlindSpot`.
- **`reallocation`** --- given current AI-effort distribution, rank hypothetical reallocations by suffering-reduction per unit of compute.
- **`camp_analysis`** --- for a given intervention, identify blockers / accelerants, enumerate bridges.
- **`leverage`** --- rank interventions by leverage × friction-robustness, optionally constrained to specified coalitions.
- **`blindspot`** --- cross-check operator priors against camp graph, flag under-weighted positions.

## Output

- **Canonical:** JSON under `public-output/analyses/<query>_<timestamp>.json`. Schema-validated. This is what the tool _means_.
- **Shaped:** markdown prose companion generated by a Claude pass over the canonical JSON, constrained by directives-ai voice rules. This is what ships to readers.

Astro route `src/pages/analyses/[id].astro` uses `getStaticPaths` to enumerate JSON artifacts at build time.

## Operator priors

`data/priors/grant.yaml` encodes BRAIN.md as a prior set --- explicit axiom leans (e/acc + 80K-EA overlay + poker-EV), stated blind spots (true vs. operative), known defections (AI at work vs. stated ideal). The `BlindSpot` query cross-references this against the camp graph rather than trusting the operator to notice their own under-weightings.

## Integration with existing tooling

- `Taskfile.yml` gains `engine:install`, `engine:test`, `engine:check`, `engine:cli`. `engine:check` joins the existing `task check` fan-out so pre-push validates engine code.
- `.gitignore` extended for Python/uv artifacts and `data/afls.db`.
- `lefthook.yml` unchanged at MVP (pre-commit badge / emdash / author checks still fire).
- Cloudflare Pages deploy workflow unchanged --- it already runs `pnpm build`, which now picks up `public-output/` via the new Astro route.
- `~/git/grantklassy/tools/update-last-updated` handles badge non-substantive-commit classification; no reinvention.

## What this is not

- Not multi-operator. Not web-hosted. Not a platform. Not a framework for others to extend.
- Not opinionated about ethics. The axiom-family enum is plural by design; the tool reasons over coalitions, not from a fixed ethics.
- Not an EA-modeling DSL. No suffering-reduction scoring function smuggled in. Leverage and confidence are operator-authored; the tool structures and cross-references.
- Not an oracle. LLM passes are fallible; validation catches malformed outputs, not wrong ones. Operator review remains load-bearing.

## Test anchor

The Palantir query is the living acceptance test. If the architecture ever stops producing a clean Palantir analysis --- descriptive convergence, normative divergence, named bridges, honest blindspot flag --- the architecture is wrong.
