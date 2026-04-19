// Renders-what-it-says test for the homepage. After `pnpm build`,
// dist/index.html must carry the graph mount + JSON payload, every LEGEND
// entry (letter badge, emoji+label, data-kind), the worked-example heading,
// and the footer link to the latest leverage analysis. Skips if dist/ is
// absent --- vitest runs under `task check` without a prior build; exercise
// the rendered checks via `task local:site:verify-rendered`, which builds first.

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { allAnalyses } from "./graph";
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

  it("links to the latest leverage analysis in the footer", () => {
    const latest = latestLeverageFrom(allAnalyses() as AnalysisEntry[]);
    if (!latest) {
      throw new Error("no leverage analysis found; cannot assert link");
    }
    expect(html).toContain(`/analyses/${latest.id}/`);
  });

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
