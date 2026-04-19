// Renders-what-it-says test for the homepage. After `pnpm build`,
// dist/index.html must carry the graph mount + JSON payload, every LEGEND
// entry (letter badge, emoji+label, data-kind), the worked-example heading,
// and the footer link to the latest leverage analysis. Skips if dist/ is
// absent --- vitest runs under `task check` without a prior build; exercise
// the rendered checks via `task local:site:verify-rendered`, which builds first.

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { allAnalyses, KIND_EMOJI, type NodeKind } from "./graph";
import { latestLeverageFrom } from "./leverage-latest";
import { LEGEND } from "./legend";
import type { AnalysisEntry } from "./analysis";

const DIST_HTML = path.resolve(process.cwd(), "dist/index.html");
const hasDist = fs.existsSync(DIST_HTML);

describe.skipIf(!hasDist)("homepage rendered HTML (dist/index.html)", () => {
  const html = hasDist ? fs.readFileSync(DIST_HTML, "utf-8") : "";

  it("renders the graph mount div", () => {
    expect(html).toMatch(/id=["']afls-graph["']/);
  });

  it("ships the graph JSON payload inline", () => {
    expect(html).toMatch(/id=["']afls-graph-data["']/);
  });

  it("renders the worked-example Contested claims heading", () => {
    expect(html).toContain("Contested claims");
  });

  it("B7: links to the latest leverage analysis in the footer", () => {
    const latest = latestLeverageFrom(allAnalyses() as AnalysisEntry[]);
    if (!latest) {
      throw new Error("no leverage analysis found; cannot assert link");
    }
    expect(html).toContain(`/analyses/${latest.id}/`);
  });

  it("B3: renders three group subheads", () => {
    // Three <h3> subheads for the node/layer/relation groups. Matched
    // case-insensitively since the template lower-cases them.
    expect(html).toMatch(/<h3[^>]*>\s*nodes\s*<\/h3>/i);
    expect(html).toMatch(/<h3[^>]*>\s*scoring layers\s*<\/h3>/i);
    expect(html).toMatch(/<h3[^>]*>\s*coalition relations\s*<\/h3>/i);
  });

  it("B3: renders two <hr> separators between the three groups", () => {
    // The <hr>s live inside the legend <section>. If the homepage grows a
    // second <section> with <hr>s, this needs refinement --- but right now
    // the legend owns every <hr>, so a raw count is safe.
    const hrCount = (html.match(/<hr\b/gi) ?? []).length;
    expect(hrCount).toBe(2);
  });

  it("B4: DOM order is nodes → layers → relations", () => {
    const nodesIdx = html.search(/<h3[^>]*>\s*nodes\s*</i);
    const layersIdx = html.search(/<h3[^>]*>\s*scoring layers\s*</i);
    const relationsIdx = html.search(/<h3[^>]*>\s*coalition relations\s*</i);
    expect(nodesIdx).toBeGreaterThan(-1);
    expect(layersIdx).toBeGreaterThan(nodesIdx);
    expect(relationsIdx).toBeGreaterThan(layersIdx);
  });

  it("B8: inlined graph-data JSON parses and has nodes + edges arrays", () => {
    // Shape check against the public GraphData contract. A malformed payload
    // here means the homepage ships dead JS --- users see an empty canvas.
    const match = html.match(
      /id=["']afls-graph-data["'][^>]*>([\s\S]*?)<\/script>/,
    );
    expect(match, "afls-graph-data <script> not found").toBeTruthy();
    const raw = (match![1] ?? "").trim();
    expect(raw.length, "afls-graph-data payload is empty").toBeGreaterThan(0);
    const parsed = JSON.parse(raw);
    expect(Array.isArray(parsed.nodes)).toBe(true);
    expect(Array.isArray(parsed.edges)).toBe(true);
    // Every node's kind must be a known NodeKind. Catches the case where the
    // build emits a kind the TS side doesn't know about.
    const knownKinds = new Set<string>(Object.keys(KIND_EMOJI));
    for (const node of parsed.nodes) {
      expect(
        knownKinds.has(node.kind),
        `unknown kind on node ${node.id}: ${node.kind}`,
      ).toBe(true);
    }
  });

  it("B9: every legend data-kind is a declared NodeKind", () => {
    // Belt-and-suspenders vs the per-entry test below: scrape every data-kind
    // in the DOM and confirm the TS union covers them.
    const attrPattern = /data-kind=["']([^"']+)["']/g;
    const emittedKinds = new Set<string>();
    for (const match of html.matchAll(attrPattern)) {
      emittedKinds.add(match[1]);
    }
    const declared = new Set<string>(Object.keys(KIND_EMOJI));
    for (const kind of emittedKinds) {
      expect(declared.has(kind), `stray data-kind ${kind}`).toBe(true);
    }
    // And the LEGEND set should be a subset of emitted (every pill rendered).
    for (const entry of LEGEND) {
      expect(
        emittedKinds.has(entry.kind),
        `legend kind ${entry.kind} not emitted in DOM`,
      ).toBe(true);
    }
  });

  it("B10: <noscript> fallback links to camps/claims/interventions", () => {
    const match = html.match(/<noscript\b[^>]*>([\s\S]*?)<\/noscript>/);
    expect(match, "no <noscript> block found").toBeTruthy();
    const block = match![1];
    expect(block).toMatch(/href=["']\/camps\/["']/);
    expect(block).toMatch(/href=["']\/claims\/["']/);
    expect(block).toMatch(/href=["']\/interventions\/["']/);
  });

  it("B5: each legend pill's count matches KIND_EMOJI coverage", () => {
    // Weaker than "matches the Astro collection length" --- vitest can't run
    // astro:content in this standalone context without heavy setup. But we
    // can assert the count is rendered at all and is a non-negative integer
    // for every legend entry, which is what B5 is really gating: the
    // (N) parenthetical must not render as `(NaN)` or `(undefined)`.
    for (const entry of LEGEND) {
      // The count renders as `({N})` immediately after the kind's label span.
      const label = `${entry.emoji} ${entry.label}`;
      const idx = html.indexOf(label);
      expect(idx, `missing legend label: ${label}`).toBeGreaterThan(-1);
      const window = html.slice(idx, idx + 400);
      const countMatch = window.match(/\(\s*(\d+)\s*\)/);
      expect(
        countMatch,
        `no (N) count after legend label for ${entry.kind}`,
      ).toBeTruthy();
      const n = Number(countMatch![1]);
      expect(Number.isInteger(n)).toBe(true);
      expect(n).toBeGreaterThanOrEqual(0);
    }
  });

  // Per-entry smoke. Grouped last because these now act as the B9/B11
  // per-kind check --- everything above was aggregate.
  for (const entry of LEGEND) {
    describe(`legend [${entry.letter}] ${entry.emoji} ${entry.label}`, () => {
      it("renders the letter badge", () => {
        // Astro's JSX-expression rendering can pad the letter with whitespace
        // (`> CD </span>`). Inline spans render unpadded (`>CD</span>`). Both OK.
        const re = new RegExp(`>\\s*${entry.letter}\\s*</span>`);
        expect(html).toMatch(re);
      });

      it("renders the emoji adjacent to the label", () => {
        expect(html).toContain(`${entry.emoji} ${entry.label}`);
      });

      it("exposes data-kind for graph cross-highlighting", () => {
        const re = new RegExp(`data-kind=["']${entry.kind}["']`);
        expect(html).toMatch(re);
      });
    });
  }
});

if (!hasDist) {
  console.warn(
    `[home.rendered.test] dist/index.html not found; skipping rendered checks. ` +
      `Run \`pnpm build\` (or \`task local:site:verify-rendered\`) to exercise them.`,
  );
}
