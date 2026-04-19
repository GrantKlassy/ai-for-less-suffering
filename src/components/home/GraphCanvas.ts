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
    source: 22,
    friction_layer: 22,
    harm_layer: 22,
    suffering_layer: 22,
    descriptive_claim: 18,
    normative_claim: 18,
    evidence: 16,
  };

  const cy = cytoscape({
    container: mount,
    elements: [
      ...data.nodes.map((n: GraphNode) => ({
        data: {
          id: n.id,
          label: n.emoji ? `${n.emoji} ${n.label}` : n.label,
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
        return (
          {
            intervention: 3,
            camp: 2,
            normative_claim: 1,
            descriptive_claim: 0,
          }[kind] ?? 0
        );
      },
      levelWidth: () => 1,
      spacingFactor: 1.4,
      minNodeSpacing: 28,
      avoidOverlap: true,
      padding: 32,
      animate: false,
    },
    minZoom: 0.2,
    maxZoom: 3,
  });

  cy.on("tap", "node", (event: cytoscape.EventObject) => {
    const node = event.target as NodeSingular;
    const href = node.data("href") as string | undefined;
    if (href) window.location.href = href;
  });

  cy.on("mouseover", "node", (event: cytoscape.EventObject) => {
    const node = event.target as NodeSingular;
    const neighborhood = node.closedNeighborhood();
    cy.elements().addClass("faded");
    neighborhood.removeClass("faded").addClass("highlight");
  });

  cy.on("mouseout", "node", () => {
    cy.elements().removeClass("faded").removeClass("highlight");
  });

  cy.on("mouseover", "edge", (event: cytoscape.EventObject) => {
    const edge = event.target as EdgeSingular;
    const ends = edge.connectedNodes();
    cy.elements().addClass("faded");
    ends.removeClass("faded").addClass("highlight");
    edge.removeClass("faded").addClass("highlight");
  });

  cy.on("mouseout", "edge", () => {
    cy.elements().removeClass("faded").removeClass("highlight");
  });

  return cy;
}
