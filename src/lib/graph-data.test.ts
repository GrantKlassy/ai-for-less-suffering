import { describe, expect, it } from "vitest";

import { NODE_KIND_COLOR } from "./legend";
import { buildGraphData } from "./graph-data";

const fixture = {
  camps: [
    {
      id: "camp_anthropic",
      name: "Anthropic",
      held_descriptive: ["desc_grid", "desc_accelerating"],
      held_normative: ["norm_safety"],
    },
    {
      id: "camp_xrisk",
      name: "x-risk",
      held_descriptive: ["desc_accelerating"],
      held_normative: [],
    },
  ],
  claims: [
    {
      id: "desc_grid",
      text: "grid is the bind",
      kind: "descriptive_claim" as const,
    },
    {
      id: "desc_accelerating",
      text: "AI is accelerating",
      kind: "descriptive_claim" as const,
    },
    {
      id: "norm_safety",
      text: "safety first",
      kind: "normative_claim" as const,
    },
  ],
  interventions: [
    { id: "intv_compute", text: "scale compute" },
    { id: "intv_alignment_research", text: "alignment research" },
  ],
  coalitions: [
    {
      intervention_id: "intv_compute",
      supporting_camps: ["camp_anthropic"],
      contesting_camps: ["camp_xrisk"],
      expected_friction: "",
    },
  ],
};

describe("buildGraphData", () => {
  it("emits a node per unique id across collections", () => {
    const out = buildGraphData(fixture);
    const ids = out.nodes.map((n) => n.id).sort();
    expect(ids).toEqual(
      [
        "camp_anthropic",
        "camp_xrisk",
        "desc_accelerating",
        "desc_grid",
        "intv_alignment_research",
        "intv_compute",
        "norm_safety",
      ].sort(),
    );
  });

  it("pulls node fill color from NODE_KIND_COLOR", () => {
    const out = buildGraphData(fixture);
    for (const node of out.nodes) {
      expect(node.color).toBe(NODE_KIND_COLOR[node.kind].fill);
    }
  });

  it("uses the camp emoji for camp nodes, kind emoji otherwise", () => {
    const out = buildGraphData(fixture);
    const anthropic = out.nodes.find((n) => n.id === "camp_anthropic")!;
    expect(anthropic.emoji).toBe("🧡");
    const claim = out.nodes.find((n) => n.id === "desc_grid")!;
    expect(claim.emoji).toBe("✅");
  });

  it("emits one edge per held_descriptive entry per camp", () => {
    const out = buildGraphData(fixture);
    const heldDesc = out.edges.filter((e) => e.kind === "held_descriptive");
    expect(heldDesc).toHaveLength(3);
    expect(
      heldDesc.find(
        (e) => e.source === "camp_anthropic" && e.target === "desc_grid",
      ),
    ).toBeDefined();
  });

  it("emits supports/contests edges from coalition analyses", () => {
    const out = buildGraphData(fixture);
    const supports = out.edges.filter((e) => e.kind === "supports");
    const contests = out.edges.filter((e) => e.kind === "contests");
    expect(supports).toHaveLength(1);
    expect(supports[0]).toMatchObject({
      source: "intv_compute",
      target: "camp_anthropic",
    });
    expect(contests).toHaveLength(1);
    expect(contests[0]).toMatchObject({
      source: "intv_compute",
      target: "camp_xrisk",
    });
  });

  it("produces no duplicate node ids", () => {
    const out = buildGraphData(fixture);
    const ids = out.nodes.map((n) => n.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("drops edges whose endpoints are missing from the node set", () => {
    const out = buildGraphData({
      ...fixture,
      camps: [
        {
          id: "camp_anthropic",
          name: "Anthropic",
          held_descriptive: ["desc_nonexistent"],
          held_normative: [],
        },
      ],
      claims: [],
      coalitions: [],
    });
    const heldDesc = out.edges.filter((e) => e.kind === "held_descriptive");
    expect(heldDesc).toHaveLength(0);
  });
});
