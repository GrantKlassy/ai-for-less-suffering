// Client-side cytoscape bootstrap. Mounted by GraphView.astro via a module
// script tag. Reads a same-page application/json payload element, configures
// cytoscape with a cose layout, and wires click-to-navigate plus hover-to-
// highlight neighbors.
//
// Why a module script vs. client:visible: vanilla TS islands in Astro use
// bundled ES module script tags, not framework directives. The cytoscape
// bundle is large (~400KB); we pay that cost once and get drag/zoom/click
// cheaply. If this ever becomes a bottleneck, wrap the import() in an
// IntersectionObserver gate.

import cytoscape from "cytoscape";
import type { Core, EdgeSingular, NodeSingular } from "cytoscape";

import type { GraphData, GraphNode, GraphEdge } from "../../lib/graph-data";
import type { NodeKind } from "../../lib/graph";

export function initGraph(mountId: string, dataId: string): Core | null {
  const mount = document.getElementById(mountId);
  const dataEl = document.getElementById(dataId);
  if (!mount || !dataEl) {
    console.warn("afls-graph: mount or data element missing");
    return null;
  }

  const raw = dataEl.textContent ?? "";
  let data: GraphData;
  try {
    data = JSON.parse(raw) as GraphData;
  } catch (err) {
    console.error("afls-graph: failed to parse graph data", err);
    return null;
  }

  const kindSize: Record<string, number> = {
    intervention: 44,
    camp: 36,
    friction_layer: 26,
    harm_layer: 26,
    suffering_layer: 26,
    convergence: 24,
    bridge: 22,
    blindspot: 20,
    descriptive_claim: 18,
    normative_claim: 18,
    source: 14,
    evidence: 12,
  };

  const cy = cytoscape({
    container: mount,
    elements: [
      ...data.nodes.map((n: GraphNode) => ({
        data: {
          id: n.id,
          label: n.emoji ? `${n.emoji} ${n.label}` : n.label,
          fullLabel: n.emoji ? `${n.emoji} ${n.fullLabel}` : n.fullLabel,
          kind: n.kind,
          color: n.color,
          href: n.href,
          size: kindSize[n.kind] ?? 20,
        },
      })),
      ...data.edges.map((e: GraphEdge) => ({
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          kind: e.kind,
        },
      })),
    ],
    style: [
      {
        selector: "node",
        style: {
          "background-color": "data(color)",
          "border-width": 1,
          "border-color": "#18181b",
          label: "data(label)",
          "font-family": "ui-monospace, SFMono-Regular, Menlo, monospace",
          "font-size": 10,
          color: "#e4e4e7",
          "text-outline-width": 2,
          "text-outline-color": "#09090b",
          "text-valign": "bottom",
          "text-margin-y": 4,
          "text-wrap": "wrap",
          "text-max-width": "140px",
          width: "data(size)",
          height: "data(size)",
        },
      },
      {
        selector: 'node[kind = "intervention"]',
        style: {
          shape: "diamond",
          "border-color": "#10b981",
          "border-width": 2,
        },
      },
      {
        selector: 'node[kind = "camp"]',
        style: {
          shape: "round-rectangle",
          "border-color": "#52525b",
          "border-width": 2,
        },
      },
      {
        // Relation nodes take distinct shapes so they read as structurally
        // different from concrete nodes (camp = round-rect, intervention =
        // diamond). Bridge is a hexagon (two sides, translation between);
        // convergence is an octagon (many sides converging on one point);
        // blindspot is a vee (pointing at what is missed).
        selector: 'node[kind = "bridge"]',
        style: {
          shape: "hexagon",
          "border-color": "#22d3ee",
          "border-width": 2,
        },
      },
      {
        selector: 'node[kind = "convergence"]',
        style: {
          shape: "octagon",
          "border-color": "#a3e635",
          "border-width": 2,
        },
      },
      {
        selector: 'node[kind = "blindspot"]',
        style: {
          shape: "vee",
          "border-color": "#f472b6",
          "border-width": 2,
        },
      },
      {
        selector: "edge",
        style: {
          width: 1,
          "line-color": "#3f3f46",
          "curve-style": "bezier",
          "target-arrow-color": "#3f3f46",
          "target-arrow-shape": "triangle",
          "arrow-scale": 0.6,
          opacity: 0.6,
        },
      },
      {
        selector: 'edge[kind = "supports"]',
        style: {
          "line-color": "#10b981",
          "target-arrow-color": "#10b981",
          opacity: 0.7,
        },
      },
      {
        selector: 'edge[kind = "contests"]',
        style: {
          "line-color": "#f43f5e",
          "target-arrow-color": "#f43f5e",
          "line-style": "dashed",
          opacity: 0.7,
        },
      },
      {
        selector: 'edge[kind = "cites_source"]',
        style: {
          "line-color": "#71717a",
          "target-arrow-color": "#71717a",
          width: 0.5,
          opacity: 0.35,
        },
      },
      {
        selector: 'edge[kind = "stance_support"]',
        style: {
          "line-color": "#10b981",
          "target-arrow-color": "#10b981",
          opacity: 0.6,
        },
      },
      {
        selector: 'edge[kind = "stance_contradict"]',
        style: {
          "line-color": "#f43f5e",
          "target-arrow-color": "#f43f5e",
          "line-style": "dashed",
          opacity: 0.6,
        },
      },
      {
        selector: 'edge[kind = "stance_qualify"]',
        style: {
          "line-color": "#f59e0b",
          "target-arrow-color": "#f59e0b",
          "line-style": "dotted",
          opacity: 0.6,
        },
      },
      {
        selector: 'edge[kind = "scores_friction"]',
        style: {
          "line-color": "#f97316",
          "target-arrow-color": "#f97316",
          opacity: 0.5,
        },
      },
      {
        selector: 'edge[kind = "scores_harm"]',
        style: {
          "line-color": "#f43f5e",
          "target-arrow-color": "#f43f5e",
          opacity: 0.5,
        },
      },
      {
        selector: 'edge[kind = "relieves_suffering"]',
        style: {
          "line-color": "#10b981",
          "target-arrow-color": "#10b981",
          opacity: 0.6,
        },
      },
      {
        // Bridge edges are dotted cyan. Dotted reads as "partial translation"
        // --- not a full semantic equivalence.
        selector: 'edge[kind = "bridge_from"], edge[kind = "bridge_to"]',
        style: {
          "line-color": "#67e8f9",
          "target-arrow-color": "#67e8f9",
          "line-style": "dotted",
          opacity: 0.6,
        },
      },
      {
        selector: 'edge[kind = "converges_on"], edge[kind = "converges_camp"]',
        style: {
          "line-color": "#a3e635",
          "target-arrow-color": "#a3e635",
          opacity: 0.6,
        },
      },
      {
        // The normative thread through a convergence is qualitatively
        // different --- dashed to mark it as reasoning, not structure.
        selector: 'edge[kind = "converges_via_norm"]',
        style: {
          "line-color": "#a3e635",
          "target-arrow-color": "#a3e635",
          "line-style": "dashed",
          opacity: 0.5,
        },
      },
      {
        selector: 'edge[kind = "flags_camp"]',
        style: {
          "line-color": "#f9a8d4",
          "target-arrow-color": "#f9a8d4",
          "line-style": "dashed",
          opacity: 0.6,
        },
      },
      {
        selector: ".faded",
        style: {
          opacity: 0.08,
          "text-opacity": 0,
        },
      },
      {
        selector: ".highlight",
        style: {
          opacity: 1,
          "border-color": "#fafafa",
          "border-width": 2,
          "text-opacity": 1,
          "z-index": 10,
        },
      },
      {
        // Hover/legend-pill highlight swaps in the full label so nothing reads
        // as "…" when the user is actually trying to see what a node says.
        selector: "node.highlight",
        style: {
          label: "data(fullLabel)",
          "text-max-width": "280px",
        },
      },
      {
        selector: "edge.highlight",
        style: {
          "line-color": "#fafafa",
          "target-arrow-color": "#fafafa",
          width: 2,
          opacity: 1,
        },
      },
    ],
    layout: {
      name: "concentric",
      concentric: (node: NodeSingular) => {
        const kind = node.data("kind") as string;
        // Higher value = closer to center. Interventions sit at the core
        // (they're the thing being evaluated). Layers ring them directly
        // (friction/harm/suffering score interventions). Relation nodes
        // share the camp ring --- convergences link camps to interventions,
        // bridges connect camp-to-camp, blindspots flag a camp. Claims
        // flank outward. Evidence + sources form the outer atmosphere of
        // citations so every kind gets its own ring when a pill highlights.
        return (
          {
            intervention: 7,
            suffering_layer: 6,
            friction_layer: 6,
            harm_layer: 6,
            convergence: 5,
            camp: 5,
            bridge: 5,
            blindspot: 5,
            normative_claim: 4,
            descriptive_claim: 3,
            evidence: 2,
            source: 1,
          }[kind] ?? 0
        );
      },
      levelWidth: () => 1,
      spacingFactor: 1.25,
      minNodeSpacing: 18,
      avoidOverlap: true,
      padding: 32,
      animate: false,
    },
    minZoom: 0.2,
    maxZoom: 3,
    // Cytoscape's default wheel step is tiny --- one scroll tick barely moves
    // the zoom. 2.5x makes the graph respond more like a normal map.
    wheelSensitivity: 2.5,
  });

  cy.on("tap", "node", (event: cytoscape.EventObject) => {
    const node = event.target as NodeSingular;
    const href = node.data("href") as string | undefined;
    if (href) window.location.href = href;
  });

  // Right-click drag pans the graph, regardless of what's under the cursor.
  // Cytoscape only pans on left-drag-on-empty and drags nodes on left-drag-on-
  // node --- there's no built-in right-drag-pan. Native listeners at the mount
  // in capture phase intercept before cytoscape, and window-level move/up track
  // drags that leave the mount.
  let isRightPanning = false;
  let lastX = 0;
  let lastY = 0;

  mount.addEventListener(
    "mousedown",
    (e) => {
      if (e.button !== 2) return;
      isRightPanning = true;
      lastX = e.clientX;
      lastY = e.clientY;
      cy.elements().removeClass("faded").removeClass("highlight");
      e.preventDefault();
      e.stopPropagation();
    },
    true,
  );
  window.addEventListener("mousemove", (e) => {
    if (!isRightPanning) return;
    const dx = e.clientX - lastX;
    const dy = e.clientY - lastY;
    lastX = e.clientX;
    lastY = e.clientY;
    cy.panBy({ x: dx, y: dy });
  });
  window.addEventListener(
    "mouseup",
    (e) => {
      if (e.button !== 2 || !isRightPanning) return;
      isRightPanning = false;
      e.preventDefault();
      e.stopPropagation();
    },
    true,
  );
  mount.addEventListener("contextmenu", (e) => e.preventDefault());

  cy.on("mouseover", "node", (event: cytoscape.EventObject) => {
    if (isRightPanning) return;
    const node = event.target as NodeSingular;
    const neighborhood = node.closedNeighborhood();
    cy.elements().addClass("faded");
    neighborhood.removeClass("faded").addClass("highlight");
  });

  cy.on("mouseout", "node", () => {
    if (isRightPanning) return;
    cy.elements().removeClass("faded").removeClass("highlight");
  });

  cy.on("mouseover", "edge", (event: cytoscape.EventObject) => {
    if (isRightPanning) return;
    const edge = event.target as EdgeSingular;
    const ends = edge.connectedNodes();
    cy.elements().addClass("faded");
    ends.removeClass("faded").addClass("highlight");
    edge.removeClass("faded").addClass("highlight");
  });

  cy.on("mouseout", "edge", () => {
    if (isRightPanning) return;
    cy.elements().removeClass("faded").removeClass("highlight");
  });

  return cy;
}

// Cross-highlight entry point for the legend. `null` clears; otherwise fade
// everything, unfade the closed neighborhood of matching-kind nodes, and ring
// only the matching nodes. This mirrors node-hover semantics so pill-hover and
// node-hover produce the same visual shape --- a connected sub-cluster against
// a dimmed background --- instead of pill-hover's old behavior where matching
// nodes were ringed but every edge in the graph stayed lit in its native color.
export function highlightKind(cy: Core, kind: NodeKind | null): void {
  cy.elements().removeClass("faded").removeClass("highlight");
  if (kind === null) return;
  const matching = cy.nodes(`[kind = "${kind}"]`);
  cy.elements().addClass("faded");
  matching.closedNeighborhood().removeClass("faded");
  matching.addClass("highlight");
}
