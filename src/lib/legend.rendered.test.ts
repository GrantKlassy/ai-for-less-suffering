// Renders-what-it-says test: after `pnpm build`, every legend entry in
// dist/index.html has (a) its letter badge span and (b) its emoji + label
// co-located as displayed text. Catches the "added a NodeKind but forgot to
// wire it into the homepage" failure mode that the structural test can't see.
//
// Skips with a console hint if dist/ is absent --- vitest runs under
// `task check` without a prior build. Wire the rendered assertion into the
// ship flow via `task site:verify-rendered`, which builds first.

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { LEGEND } from "./legend";

const DIST_HTML = path.resolve(process.cwd(), "dist/index.html");
const hasDist = fs.existsSync(DIST_HTML);

describe.skipIf(!hasDist)("homepage rendered HTML (dist/index.html)", () => {
  const html = hasDist ? fs.readFileSync(DIST_HTML, "utf-8") : "";

  for (const entry of LEGEND) {
    describe(`[${entry.letter}] ${entry.emoji} ${entry.label}`, () => {
      it("renders the letter badge", () => {
        // Astro's JSX-expression rendering can pad the letter with whitespace
        // (e.g., `> CD </span>`), so allow it. Inline spans from NodeRef.astro
        // render without padding (`>CD</span>`) --- both forms are accepted.
        const re = new RegExp(`>\\s*${entry.letter}\\s*</span>`);
        expect(html).toMatch(re);
      });

      it("renders the emoji adjacent to the label", () => {
        // Homepage template: `{emoji} {label}` --- single space separator.
        expect(html).toContain(`${entry.emoji} ${entry.label}`);
      });
    });
  }
});

if (!hasDist) {
  console.warn(
    `[legend.rendered.test] dist/index.html not found; skipping rendered checks. ` +
      `Run \`pnpm build\` (or \`task site:verify-rendered\`) to exercise them.`,
  );
}
