import { describe, expect, it } from "vitest";

import { KIND_EMOJI, type NodeKind } from "./graph";
import { LEGEND } from "./legend";

describe("LEGEND", () => {
  it("has no duplicate letters", () => {
    const letters = LEGEND.map((e) => e.letter);
    expect(new Set(letters).size).toBe(letters.length);
  });

  it("has no duplicate kinds", () => {
    const kinds = LEGEND.map((e) => e.kind);
    expect(new Set(kinds).size).toBe(kinds.length);
  });

  it("covers every NodeKind declared in graph.ts", () => {
    const covered = new Set(LEGEND.map((e) => e.kind));
    const declared = Object.keys(KIND_EMOJI) as NodeKind[];
    for (const k of declared) expect(covered.has(k)).toBe(true);
  });

  it("emoji on each entry matches KIND_EMOJI for that kind", () => {
    for (const e of LEGEND) expect(e.emoji).toBe(KIND_EMOJI[e.kind]);
  });

  it("has non-empty letter, label, blurb, classes on every entry", () => {
    for (const e of LEGEND) {
      expect(e.letter.length).toBeGreaterThan(0);
      expect(e.label.length).toBeGreaterThan(0);
      expect(e.blurb.length).toBeGreaterThan(0);
      expect(e.classes.length).toBeGreaterThan(0);
    }
  });
});
