import { describe, expect, it } from "vitest";

import { KIND_EMOJI, type NodeKind } from "./graph";
import { NODE_KIND_COLOR } from "./legend";
import {
  buildGraphData,
  HOME_GRAPH_KINDS,
  LAYER_EDGE_MIN_SCORE,
} from "./graph-data";
import type { BuildGraphDataInput } from "./graph-data";

const fixture: BuildGraphDataInput = {
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
    {
      id: "intv_compute",
      text: "scale compute",
      friction_scores: { friction_grid: 0.8, friction_permitting: 0.2 },
      harm_scores: { harm_emissions: 0.6 },
      suffering_reduction_scores: { suffering_material_scarcity: 0.7 },
    },
    {
      id: "intv_alignment_research",
      text: "alignment research",
      friction_scores: {},
      harm_scores: {},
      suffering_reduction_scores: {},
    },
  ],
  sources: [
    { id: "src_paper", title: "A paper" },
    { id: "src_report", title: "A report" },
  ],
  evidence: [
    {
      id: "evi_supports_grid",
      claim_id: "desc_grid",
      source_id: "src_paper",
      stance: "support",
      locator: "p. 3",
    },
    {
      id: "evi_contradicts_grid",
      claim_id: "desc_grid",
      source_id: "src_report",
      stance: "contradict",
      locator: "table 2",
    },
    {
      id: "evi_qualifies_accel",
      claim_id: "desc_accelerating",
      source_id: "src_paper",
      stance: "qualify",
      locator: "",
    },
  ],
  frictionLayers: [
    { id: "friction_grid", name: "grid capacity" },
    { id: "friction_permitting", name: "permitting" },
  ],
  harmLayers: [{ id: "harm_emissions", name: "emissions" }],
  sufferingLayers: [
    { id: "suffering_material_scarcity", name: "material scarcity" },
  ],
  bridges: [],
  convergences: [],
  blindspots: [],
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
        "evi_contradicts_grid",
        "evi_qualifies_accel",
        "evi_supports_grid",
        "friction_grid",
        "friction_permitting",
        "harm_emissions",
        "intv_alignment_research",
        "intv_compute",
        "norm_safety",
        "src_paper",
        "src_report",
        "suffering_material_scarcity",
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

  it("emits cites_source edge from every evidence to its source", () => {
    const out = buildGraphData(fixture);
    const cites = out.edges.filter((e) => e.kind === "cites_source");
    expect(cites).toHaveLength(3);
    expect(
      cites.find(
        (e) => e.source === "evi_supports_grid" && e.target === "src_paper",
      ),
    ).toBeDefined();
  });

  it("emits stance-typed edges from evidence to the claim it cites", () => {
    const out = buildGraphData(fixture);
    const supportStance = out.edges.filter((e) => e.kind === "stance_support");
    const contradictStance = out.edges.filter(
      (e) => e.kind === "stance_contradict",
    );
    const qualifyStance = out.edges.filter((e) => e.kind === "stance_qualify");
    expect(supportStance).toHaveLength(1);
    expect(supportStance[0]).toMatchObject({
      source: "evi_supports_grid",
      target: "desc_grid",
    });
    expect(contradictStance).toHaveLength(1);
    expect(contradictStance[0]).toMatchObject({
      source: "evi_contradicts_grid",
      target: "desc_grid",
    });
    expect(qualifyStance).toHaveLength(1);
    expect(qualifyStance[0]).toMatchObject({
      source: "evi_qualifies_accel",
      target: "desc_accelerating",
    });
  });

  it("emits scored intervention→layer edges only at or above the min-score threshold", () => {
    const out = buildGraphData(fixture);
    const friction = out.edges.filter((e) => e.kind === "scores_friction");
    // intv_compute scored friction_grid at 0.8 (kept) and friction_permitting
    // at 0.2 (dropped, below LAYER_EDGE_MIN_SCORE = 0.3).
    expect(friction).toHaveLength(1);
    expect(friction[0]).toMatchObject({
      source: "intv_compute",
      target: "friction_grid",
    });
    expect(LAYER_EDGE_MIN_SCORE).toBe(0.3);

    const harm = out.edges.filter((e) => e.kind === "scores_harm");
    expect(harm).toHaveLength(1);
    expect(harm[0]).toMatchObject({
      source: "intv_compute",
      target: "harm_emissions",
    });

    const relieves = out.edges.filter((e) => e.kind === "relieves_suffering");
    expect(relieves).toHaveLength(1);
    expect(relieves[0]).toMatchObject({
      source: "intv_compute",
      target: "suffering_material_scarcity",
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

  it("C5: buildGraphData is deterministic for a given input", () => {
    // Same input → same node/edge ordering + ids. Drift here means cytoscape
    // re-animates on every build (layout seed changes, user reports "the
    // graph keeps reshuffling").
    const a = buildGraphData(fixture);
    const b = buildGraphData(fixture);
    expect(b.nodes.map((n) => n.id)).toEqual(a.nodes.map((n) => n.id));
    expect(b.edges.map((e) => e.id)).toEqual(a.edges.map((e) => e.id));
  });

  it("C6: emits no duplicate edges (same source+kind+target)", () => {
    // Re-running the builder with the same camp→claim relationship declared
    // twice (e.g. a typo) must not produce two edges with the same id.
    const out = buildGraphData({
      ...fixture,
      camps: [
        {
          id: "camp_dup",
          name: "Dup",
          held_descriptive: ["desc_grid", "desc_grid"],
          held_normative: [],
        },
      ],
      coalitions: [],
    });
    const ids = out.edges.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
    const heldDesc = out.edges.filter(
      (e) =>
        e.kind === "held_descriptive" &&
        e.source === "camp_dup" &&
        e.target === "desc_grid",
    );
    expect(heldDesc).toHaveLength(1);
  });

  it("C7: emits no duplicate nodes across collections", () => {
    const out = buildGraphData(fixture);
    const ids = out.nodes.map((n) => n.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("C8: HOME_GRAPH_KINDS equals the full NodeKind set", () => {
    const declared = new Set(Object.keys(KIND_EMOJI) as NodeKind[]);
    expect(new Set(HOME_GRAPH_KINDS)).toEqual(declared);
  });

  it("C8: every NodeKind in KIND_EMOJI has a NODE_KIND_COLOR entry", () => {
    for (const kind of Object.keys(KIND_EMOJI) as NodeKind[]) {
      expect(NODE_KIND_COLOR[kind], `no color for ${kind}`).toBeDefined();
    }
  });

  it("emits coalition-relation edges for bridges/convergences/blindspots", () => {
    // Bridges/convergences/blindspots extend buildGraphData post-§3; the
    // baseline fixture has empty arrays, so a focused fixture exercises the
    // emission path without disturbing the rest of the suite.
    const out = buildGraphData({
      ...fixture,
      bridges: [
        {
          id: "bridge_ab",
          from_camp: "camp_anthropic",
          to_camp: "camp_xrisk",
          translation: "t",
        },
      ],
      convergences: [
        {
          id: "conv_compute",
          intervention_id: "intv_compute",
          camps: ["camp_anthropic", "camp_xrisk"],
          divergent_reasons: { camp_anthropic: "norm_safety" },
        },
      ],
      blindspots: [
        {
          id: "blind_x",
          flagged_camp_id: "camp_anthropic",
          against_prior_set: "some priors",
        },
      ],
    });
    expect(out.edges.filter((e) => e.kind === "bridge_from")).toHaveLength(1);
    expect(out.edges.filter((e) => e.kind === "bridge_to")).toHaveLength(1);
    expect(out.edges.filter((e) => e.kind === "converges_on")).toHaveLength(1);
    expect(out.edges.filter((e) => e.kind === "converges_camp")).toHaveLength(
      2,
    );
    expect(
      out.edges.filter((e) => e.kind === "converges_via_norm"),
    ).toHaveLength(1);
    expect(out.edges.filter((e) => e.kind === "flags_camp")).toHaveLength(1);
  });
});
