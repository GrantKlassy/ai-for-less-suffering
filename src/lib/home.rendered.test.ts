// Renders-what-it-says test for the rebuilt homepage. After `pnpm build`,
// dist/index.html must contain every intervention id, the latest leverage
// generated_at stamp, the graph mount/data elements, and the nav links to the
// detail pages. Skips with a hint if dist/ is absent.
//
// This replaces the retired legend.rendered.test.ts --- the home no longer
// renders a legend, so those assertions became unreachable.

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { allAnalyses } from "./graph";
import { latestLeverageFrom } from "./leverage-latest";
import type { AnalysisEntry } from "./analysis";

const DIST_HTML = path.resolve(process.cwd(), "dist/index.html");
const hasDist = fs.existsSync(DIST_HTML);

const INTERVENTION_IDS = [
  "intv_drug_discovery",
  "intv_compute",
  "intv_mental_health_triage",
  "intv_grid",
  "intv_alignment_research",
  "intv_alt_protein",
  "intv_training",
];

describe.skipIf(!hasDist)("homepage rendered HTML (dist/index.html)", () => {
  const html = hasDist ? fs.readFileSync(DIST_HTML, "utf-8") : "";

  it("renders the graph mount div", () => {
    expect(html).toMatch(/id=["']afls-graph["']/);
  });

  it("ships the graph JSON payload inline", () => {
    expect(html).toMatch(/id=["']afls-graph-data["']/);
  });

  it("renders a row for every intervention", () => {
    for (const id of INTERVENTION_IDS) {
      expect(html).toContain(`/interventions/${id}/`);
    }
  });

  it("surfaces the latest leverage generated_at stamp", () => {
    const latest = latestLeverageFrom(allAnalyses() as AnalysisEntry[]);
    if (!latest) {
      throw new Error("no leverage analysis found; cannot assert stamp");
    }
    expect(html).toContain(latest.analysis.generated_at);
  });

  it("links to the latest leverage analysis page", () => {
    const latest = latestLeverageFrom(allAnalyses() as AnalysisEntry[]);
    if (!latest) {
      throw new Error("no leverage analysis found; cannot assert link");
    }
    expect(html).toContain(`/analyses/${latest.id}/`);
  });

  it("renders the operator-position stance labels", () => {
    // At least one of these must appear --- the seed file has
    // under_consideration on every intervention; flipping stances is an
    // operator edit, not a code change.
    const anyStance = [
      "priority",
      "qualified support",
      "skeptical",
      "oppose",
      "under consideration",
    ].some((s) => html.includes(s));
    expect(anyStance).toBe(true);
  });
});

if (!hasDist) {
  console.warn(
    `[home.rendered.test] dist/index.html not found; skipping rendered checks. ` +
      `Run \`pnpm build\` to exercise them.`,
  );
}
