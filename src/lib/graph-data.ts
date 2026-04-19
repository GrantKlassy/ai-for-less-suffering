// Builds the payload the cytoscape island consumes. Pure at its core
// (buildGraphData takes data in, returns {nodes, edges} out) plus an
// Astro-land loader that pulls from content collections + the latest leverage
// analysis.
//
// Node color is sourced from NODE_KIND_COLOR in legend.ts --- one source of
// truth so the pill on a card and the fill on a graph node cannot drift.

import { getCollection } from "astro:content";
import { CAMP_EMOJI, KIND_EMOJI, type NodeKind } from "./graph";
import { NODE_KIND_COLOR } from "./legend";
import { latestLeverageAnalysis } from "./leverage-latest";
import type { InterventionCoalitionAnalysis } from "./analysis";

export interface GraphNode {
  id: string;
  kind: NodeKind;
  label: string;
  emoji: string;
  color: string;
  href: string;
}

export type EdgeKind =
  | "held_descriptive"
  | "held_normative"
  | "supports"
  | "contests";

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  kind: EdgeKind;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// Pure shape for unit tests --- callers hand in every collection's items
// directly, no `astro:content` required.
export interface CampInput {
  id: string;
  name: string;
  held_descriptive: string[];
  held_normative: string[];
}

export interface ClaimInput {
  id: string;
  text: string;
  kind: "descriptive_claim" | "normative_claim";
}

export interface InterventionInput {
  id: string;
  text: string;
}

// The home graph shows only the three kinds the operator actually thinks with:
// camps, claims, interventions. Sources and layers are graph-relevant but
// visually they orphan (no edges in the current edge set), so they go in the
// nav bar and the detail pages --- not here.
export interface BuildGraphDataInput {
  camps: CampInput[];
  claims: ClaimInput[];
  interventions: InterventionInput[];
  coalitions: InterventionCoalitionAnalysis[];
}

function truncate(s: string, max = 48): string {
  return s.length <= max ? s : s.slice(0, max - 1).trimEnd() + "…";
}

function hrefFor(kind: NodeKind, id: string): string {
  switch (kind) {
    case "camp":
      return `/camps/${id}/`;
    case "descriptive_claim":
      return `/claims/descriptive/${id}/`;
    case "normative_claim":
      return `/claims/normative/${id}/`;
    case "intervention":
      return `/interventions/${id}/`;
    case "source":
      return `/sources/${id}/`;
    case "friction_layer":
      return `/layers/friction/${id}/`;
    case "harm_layer":
      return `/layers/harm/${id}/`;
    case "suffering_layer":
      return `/layers/suffering/${id}/`;
    case "evidence":
      return "";
  }
}

function emojiFor(kind: NodeKind, id: string): string {
  if (kind === "camp") return CAMP_EMOJI[id] ?? KIND_EMOJI.camp;
  return KIND_EMOJI[kind];
}

export function buildGraphData(input: BuildGraphDataInput): GraphData {
  const nodes: GraphNode[] = [];
  const seen = new Set<string>();

  function addNode(id: string, kind: NodeKind, label: string): void {
    if (seen.has(id)) return;
    seen.add(id);
    nodes.push({
      id,
      kind,
      label: truncate(label),
      emoji: emojiFor(kind, id),
      color: NODE_KIND_COLOR[kind].fill,
      href: hrefFor(kind, id),
    });
  }

  for (const c of input.camps) addNode(c.id, "camp", c.name);
  for (const cl of input.claims) addNode(cl.id, cl.kind, cl.text);
  for (const iv of input.interventions) addNode(iv.id, "intervention", iv.text);

  const edges: GraphEdge[] = [];
  const edgeIds = new Set<string>();

  function addEdge(source: string, target: string, kind: EdgeKind): void {
    const id = `${source}__${kind}__${target}`;
    if (edgeIds.has(id)) return;
    if (!seen.has(source) || !seen.has(target)) return;
    edgeIds.add(id);
    edges.push({ id, source, target, kind });
  }

  for (const camp of input.camps) {
    for (const claimId of camp.held_descriptive) {
      addEdge(camp.id, claimId, "held_descriptive");
    }
    for (const claimId of camp.held_normative) {
      addEdge(camp.id, claimId, "held_normative");
    }
  }

  for (const coal of input.coalitions) {
    for (const campId of coal.supporting_camps) {
      addEdge(coal.intervention_id, campId, "supports");
    }
    for (const campId of coal.contesting_camps) {
      addEdge(coal.intervention_id, campId, "contests");
    }
  }

  return { nodes, edges };
}

// Astro-land loader. Reads every content collection + the latest leverage
// coalition set. Falls back gracefully if no leverage analysis exists yet
// (graph renders camps/claims/interventions but without coalition edges).
export async function loadGraphData(): Promise<GraphData> {
  const [camps, desc, norm, interventions] = await Promise.all([
    getCollection("camps"),
    getCollection("descriptiveClaims"),
    getCollection("normativeClaims"),
    getCollection("interventions"),
  ]);

  const latest = latestLeverageAnalysis();

  return buildGraphData({
    camps: camps.map((c) => ({
      id: c.data.id,
      name: c.data.name,
      held_descriptive: c.data.held_descriptive.map((r) => r.id),
      held_normative: c.data.held_normative.map((r) => r.id),
    })),
    claims: [
      ...desc.map((d) => ({
        id: d.data.id,
        text: d.data.text,
        kind: "descriptive_claim" as const,
      })),
      ...norm.map((n) => ({
        id: n.data.id,
        text: n.data.text,
        kind: "normative_claim" as const,
      })),
    ],
    interventions: interventions.map((i) => ({
      id: i.data.id,
      text: i.data.text,
    })),
    coalitions: latest ? latest.analysis.coalition_analyses : [],
  });
}
