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

  it("B1: every entry carries a group in {node, layer, relation}", () => {
    const allowed = new Set<string>(["node", "layer", "relation"]);
    for (const e of LEGEND) {
      expect(allowed.has(e.group), `bad group on ${e.kind}: ${e.group}`).toBe(
        true,
      );
    }
  });

  it("B2: layer group is exactly the three scoring layer kinds", () => {
    const layerKinds = LEGEND.filter((e) => e.group === "layer")
      .map((e) => e.kind)
      .sort();
    expect(layerKinds).toEqual(
      ["friction_layer", "harm_layer", "suffering_layer"].sort(),
    );
  });

  it("B2: relation group is exactly the three coalition-logic kinds", () => {
    const relationKinds = LEGEND.filter((e) => e.group === "relation")
      .map((e) => e.kind)
      .sort();
    expect(relationKinds).toEqual(
      ["blindspot", "bridge", "convergence"].sort(),
    );
  });

  it("B2: every group is non-empty", () => {
    for (const group of ["node", "layer", "relation"] as const) {
      expect(
        LEGEND.some((e) => e.group === group),
        `group ${group} is empty`,
      ).toBe(true);
    }
  });

  it("B12: legend has entries for bridge, convergence, blindspot", () => {
    const kinds = new Set(LEGEND.map((e) => e.kind));
    expect(kinds.has("bridge")).toBe(true);
    expect(kinds.has("convergence")).toBe(true);
    expect(kinds.has("blindspot")).toBe(true);
  });
});
