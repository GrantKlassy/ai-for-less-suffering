# data/ --- the nodes

Every YAML here is a Pydantic-validated node. Schema lives in `../engine/afls/schema/`. `extra="forbid"` is set on `BaseNode` --- no ad-hoc fields, ever. If you want to add a field, change the schema first.

## Subdirectories and prefixes

| Subdir | Prefix | Schema | Purpose |
|---|---|---|---|
| `camps/` | `camp_` | `schema/camps.py` | Coherent clusters of held claims --- agents in the reasoning |
| `claims/descriptive/` | `desc_` | `schema/claims.py` | "What is." Confidence-weighted. |
| `claims/normative/` | `norm_` | `schema/claims.py` | "What should be." Tagged with an `axiom_family`. |
| `interventions/` | `intv_` | `schema/interventions.py` | Proposed actions, scored against friction + harm |
| `sources/` | `src_` | `schema/sources.py` | Citable primary documents |
| `warrants/` | `war_` | `schema/warrants.py` | Source-to-claim edges (support / contradict / qualify) |
| `friction_layers/` | `friction_` | `schema/interventions.py` | Forces that resist interventions |
| `harm_layers/` | `harm_` | `schema/interventions.py` | Welfare/structural costs if an intervention succeeds |

## Adding a node

1. Pick the right schema and read its fields. `extra="forbid"` means you can't improvise.
2. Create the YAML at the right path with the right prefix. Filename stem = `id` field.
3. Run `task engine:cli -- validate` (or `cd engine && uv run afls validate`). Referential integrity is checked here --- every `NodeRef` in the new node must resolve to an existing file of the right kind.
4. If you're adding a camp: `CAMP_EMOJI` in `src/lib/graph.ts` must also be updated. `task check:layering` catches drift.

## Presentation belongs in `src/`, not here

Emojis, colors, icons, labels --- none of these go in YAML. `CAMP_EMOJI` in `src/lib/graph.ts` is the canonical example of how presentation attaches to data without mixing layers. Keep the boundary clean; the Pydantic `extra="forbid"` will reject the other direction anyway.

## Unused node kinds

`schema/relations.py` defines `Bridge`, `Convergence`, `BlindSpot`. These have no subdirectory yet --- coalition-logic relations are defined but unpopulated. When added, they get their own subdir (e.g. `data/bridges/`, prefix `bridge_`).
