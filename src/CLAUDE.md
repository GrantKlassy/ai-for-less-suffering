# src/ --- the presentation layer

Astro 5, Tailwind 4, TypeScript. Renders `../data/` (via `astro:content`) and `../public-output/analyses/*.json` (loaded directly via `fs`). Never mutates either; never re-validates what the engine already validated.

## Choke point: `lib/graph.ts`

`src/lib/graph.ts` is the **one place** that resolves any node id → `{href, label, kind}`. Do not duplicate this dispatch in components. If you need to render a ref, use `<NodeRef id={...} />` (which calls `resolveNode` internally) or call the helpers directly.

Key exports:

- `resolveNode(id)` --- async, content-collection-backed. Camps get their emoji prefixed here.
- `collectionForId(id)` --- pure prefix dispatch.
- `CAMP_EMOJI` / `campEmoji(id)` --- presentation-only map from camp id to emoji. **Presentation lives here, never in `../data/`**. Drift between this map and `data/camps/` is caught by `engine/tests/test_layering.py` (runs under `task check`).
- `campsHoldingDescriptive` / `campsHoldingNormative` / `warrantsForClaim` / `interventionsScoringFriction` / `interventionsScoringHarm` --- reverse lookups so every detail page has both directions of the graph.
- `analysesReferencing(id)` --- scans serialized analysis JSON for a quoted id. Safe against prefix collisions because it matches `"id"` including the quotes.

## Content collections

`content.config.ts` declares collections. Add a new collection there when adding a new node kind in `data/`. Astro auto-maps files; do not hand-roll readers.

## Page conventions

- `src/pages/<kind>/index.astro` --- list view.
- `src/pages/<kind>/[id].astro` --- detail view. Every detail page surfaces at least one reverse lookup so the graph is traversable both directions.
- `src/pages/index.astro` --- home with tiles + legend. Legend entries are hand-curated; update when adding a new node kind.

## Components

- `NodeRef.astro` --- universal id-to-link. Calls `resolveNode`. Use this instead of hard-coding `<a>` tags.
- `CampChip.astro`, `AxiomTag.astro`, `ConfidenceBar.astro`, `ScoreMatrix.astro` --- shared render primitives.
- `analyses/` --- analysis-specific components, used only by `pages/analyses/`.

## Tests

- `pnpm test` / `task site:test` --- vitest. Config at `vitest.config.ts` uses Astro's `getViteConfig` so `astro:content` resolves.
- Test file convention: `foo.test.ts` next to `foo.ts`.
- Unit-testable right now: pure helpers in `lib/graph.ts` (emoji map, prefix dispatch). `resolveNode` and reverse lookups need the Astro content runtime --- test them via page-level integration if needed, not unit tests.

## What doesn't belong here

Schema changes. Validation logic. Anything that mutates data. If you want the shape of a node to change, go to `../engine/afls/schema/`.
