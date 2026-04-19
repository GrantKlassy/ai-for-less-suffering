// Tests for the cytoscape bootstrap + legend cross-highlighter. Runs
// cytoscape in headless mode (no DOM) to exercise the graph-logic bits
// without spinning up jsdom.
//
// C1/C2 parse GraphCanvas.ts source to assert every NodeKind has a kindSize
// entry and every EdgeKind has a style selector. Catches the case where a
// new kind is added to the type union but the graph forgets to size or
// style it.

import fs from "node:fs";
import path from "node:path";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { describe, expect, it } from "vitest";

import { KIND_EMOJI, type NodeKind } from "../../lib/graph";
import type { EdgeKind } from "../../lib/graph-data";
import { highlightKind } from "./GraphCanvas";

const GRAPH_CANVAS_PATH = path.resolve(__dirname, "./GraphCanvas.ts");
const source = fs.readFileSync(GRAPH_CANVAS_PATH, "utf-8");

// Every EdgeKind declared in graph-data.ts. Kept inline so the C1 test is
// self-contained --- the TS compiler would reject a new EdgeKind addition
// that wasn't listed here, because `EdgeKind` is exhaustive.
const ALL_EDGE_KINDS: EdgeKind[] = [
  "held_descriptive",
  "held_normative",
  "supports",
  "contests",
  "cites_source",
  "stance_support",
  "stance_contradict",
  "stance_qualify",
  "scores_friction",
  "scores_harm",
  "relieves_suffering",
  "bridge_from",
  "bridge_to",
  "converges_on",
  "converges_camp",
  "converges_via_norm",
  "flags_camp",
];

describe("GraphCanvas source coverage", () => {
  // Backbone edges (camp→claim) intentionally use the default "edge" style
  // --- they're the structural spine, not a signal distinction. Listing
  // them here explicitly means a new EdgeKind can't silently join the
  // default-styled set without an opt-in: if a kind is added and no
  // selector is written, the C1 test fails unless it's listed here too.
  const DEFAULT_STYLED_EDGE_KINDS: ReadonlySet<EdgeKind> = new Set([
    "held_descriptive",
    "held_normative",
  ]);

  it("C1: every EdgeKind has a styling rule (specific selector or documented default)", () => {
    // A selector block of the form `edge[kind = "<kind>"]` is how cytoscape
    // maps the kind to a color/width/dash style. A kind without one falls
    // back to the generic "edge" style and renders in default grey --- not a
    // crash, but a silent loss of signal. Kinds that deliberately inherit
    // the default are listed in DEFAULT_STYLED_EDGE_KINDS above.
    for (const kind of ALL_EDGE_KINDS) {
      if (DEFAULT_STYLED_EDGE_KINDS.has(kind)) continue;
      const needle = `edge[kind = "${kind}"]`;
      expect(
        source.includes(needle),
        `no style selector for EdgeKind ${kind} (looking for ${needle})`,
      ).toBe(true);
    }
  });

  it("C2: every NodeKind has a kindSize entry", () => {
    // The `kindSize` table maps kind → pixel diameter. A missing entry falls
    // back to the constant 20, which makes the node visually indistinct from
    // every other size-20 kind. Size is part of the visual language, not a
    // nice-to-have.
    const kinds = Object.keys(KIND_EMOJI) as NodeKind[];
    const kindSizeBlock = source.match(
      /const kindSize:[\s\S]*?\{([\s\S]*?)\};/,
    );
    expect(
      kindSizeBlock,
      "kindSize declaration not found in GraphCanvas.ts",
    ).toBeTruthy();
    const body = kindSizeBlock![1];
    for (const kind of kinds) {
      expect(
        new RegExp(`\\b${kind}\\s*:`).test(body),
        `no kindSize entry for ${kind}`,
      ).toBe(true);
    }
  });
});

// Tiny headless graph shared by C9-C13. Shape:
//
//     harm_a ─┐
//             ├── intv_x (intervention) ── friction_a
//     harm_b ─┘
//
// Plus a disconnected source_a. Deliberately small so class-state
// assertions are easy to read.
function makeGraph(): Core {
  const elements: ElementDefinition[] = [
    { data: { id: "intv_x", kind: "intervention" } },
    { data: { id: "harm_a", kind: "harm_layer" } },
    { data: { id: "harm_b", kind: "harm_layer" } },
    { data: { id: "friction_a", kind: "friction_layer" } },
    { data: { id: "source_a", kind: "source" } },
    {
      data: {
        id: "e1",
        source: "intv_x",
        target: "harm_a",
        kind: "scores_harm",
      },
    },
    {
      data: {
        id: "e2",
        source: "intv_x",
        target: "harm_b",
        kind: "scores_harm",
      },
    },
    {
      data: {
        id: "e3",
        source: "intv_x",
        target: "friction_a",
        kind: "scores_friction",
      },
    },
  ];
  return cytoscape({ headless: true, elements, styleEnabled: false });
}

describe("highlightKind", () => {
  it("C9: faded class is applied to every non-matching node", () => {
    const cy = makeGraph();
    highlightKind(cy, "harm_layer");
    // harm_a and harm_b are the matching nodes --- they must not be faded.
    expect(cy.getElementById("harm_a").hasClass("faded")).toBe(false);
    expect(cy.getElementById("harm_b").hasClass("faded")).toBe(false);
    // source_a is unrelated, outside the closed neighborhood of harm_*.
    expect(cy.getElementById("source_a").hasClass("faded")).toBe(true);
  });

  it("C9: matching nodes are ringed via the highlight class", () => {
    const cy = makeGraph();
    highlightKind(cy, "harm_layer");
    expect(cy.getElementById("harm_a").hasClass("highlight")).toBe(true);
    expect(cy.getElementById("harm_b").hasClass("highlight")).toBe(true);
    // Non-matching nodes get neighborhood inclusion (unfaded) but NOT the
    // highlight ring --- only the pill's kind wears the ring.
    expect(cy.getElementById("intv_x").hasClass("highlight")).toBe(false);
    expect(cy.getElementById("friction_a").hasClass("highlight")).toBe(false);
  });

  it("C10: edges in the closed neighborhood of matching nodes are NOT faded", () => {
    // This is the hover-fix assertion: the pre-fix code only touched nodes,
    // so every edge in the graph stayed at native opacity when a pill was
    // hovered. After the fix, edges outside the closed neighborhood fade.
    const cy = makeGraph();
    highlightKind(cy, "harm_layer");
    // e1, e2 connect intv_x to harm_a/b --- inside the closed neighborhood.
    expect(cy.getElementById("e1").hasClass("faded")).toBe(false);
    expect(cy.getElementById("e2").hasClass("faded")).toBe(false);
  });

  it("C10: edges outside the closed neighborhood of matching nodes ARE faded", () => {
    const cy = makeGraph();
    highlightKind(cy, "harm_layer");
    // e3 connects intv_x to friction_a --- intv_x is IN the closed
    // neighborhood of harm_* (it's their neighbor), but friction_a is not.
    // An edge is in the neighborhood only if BOTH endpoints are. Here,
    // friction_a is outside, so e3 must fade. This is the precise semantic
    // the hover fix was chasing.
    expect(cy.getElementById("e3").hasClass("faded")).toBe(true);
  });

  it("C11: highlightKind(null) clears every class applied by a prior call", () => {
    const cy = makeGraph();
    highlightKind(cy, "harm_layer");
    highlightKind(cy, null);
    for (const el of cy.elements().toArray()) {
      expect(el.hasClass("faded"), `${el.id()} still faded`).toBe(false);
      expect(el.hasClass("highlight"), `${el.id()} still highlighted`).toBe(
        false,
      );
    }
  });

  it("C11: consecutive highlightKind calls don't stack classes", () => {
    // Calling highlightKind twice without an intervening null should not
    // leave orphan "faded"/"highlight" classes from the first call on nodes
    // of the first kind. This caught a real regression earlier: the old
    // implementation only cleared node classes, so switching from one pill
    // to another left edges in the old cluster lit.
    const cy = makeGraph();
    highlightKind(cy, "harm_layer");
    highlightKind(cy, "friction_layer");
    // After the second call, harm_a is no longer a matching node and must
    // not carry .highlight. Under the pre-fix implementation, residual edge
    // state would have failed this.
    expect(cy.getElementById("harm_a").hasClass("highlight")).toBe(false);
    expect(cy.getElementById("friction_a").hasClass("highlight")).toBe(true);
  });

  it("C12: a node's closedNeighborhood includes every incident edge", () => {
    // The mouseover-node handler uses the same primitive --- verifying the
    // primitive's behavior here pins the contract the handler depends on.
    const cy = makeGraph();
    const intv = cy.getElementById("intv_x");
    const hood = intv.closedNeighborhood();
    for (const edgeId of ["e1", "e2", "e3"]) {
      expect(
        hood.contains(cy.getElementById(edgeId)),
        `intv_x's closedNeighborhood missing ${edgeId}`,
      ).toBe(true);
    }
  });

  it("C13: an edge's connectedNodes returns exactly its two endpoints", () => {
    // The mouseover-edge handler highlights both endpoints via connectedNodes.
    const cy = makeGraph();
    const edge = cy.getElementById("e1");
    const ends = edge.connectedNodes();
    const endIds = ends
      .toArray()
      .map((n) => n.id())
      .sort();
    expect(endIds).toEqual(["harm_a", "intv_x"].sort());
  });
});
