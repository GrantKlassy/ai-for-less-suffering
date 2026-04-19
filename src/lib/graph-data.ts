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
  | "contests"
  | "cites_source"
  | "stance_support"
  | "stance_contradict"
  | "stance_qualify"
  | "scores_friction"
  | "scores_harm"
  | "relieves_suffering"
  // Coalition-logic edges from engine/afls/schema/relations.py.
  | "bridge_from"
  | "bridge_to"
  | "converges_on"
  | "converges_camp"
  | "converges_via_norm"
  | "flags_camp";

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
  friction_scores: Record<string, number>;
  harm_scores: Record<string, number>;
  suffering_reduction_scores: Record<string, number>;
}

export interface SourceInput {
  id: string;
  title: string;
}

export interface EvidenceInput {
  id: string;
  claim_id: string;
  source_id: string;
  stance: "support" | "contradict" | "qualify";
  locator: string;
}

export interface LayerInput {
  id: string;
  name: string;
}

export interface BridgeInput {
  id: string;
  from_camp: string;
  to_camp: string;
  translation: string;
}

export interface ConvergenceInput {
  id: string;
  intervention_id: string;
  camps: string[];
  divergent_reasons: Record<string, string>;
}

export interface BlindspotInput {
  id: string;
  flagged_camp_id: string;
  against_prior_set: string;
}

// Every NodeKind renders on the home graph. The legend pill for each kind
// isolates a distinct cluster on hover; this set is the contract.
export const HOME_GRAPH_KINDS: ReadonlySet<NodeKind> = new Set<NodeKind>([
  "camp",
  "descriptive_claim",
  "normative_claim",
  "intervention",
  "source",
  "evidence",
  "friction_layer",
  "harm_layer",
  "suffering_layer",
  "bridge",
  "convergence",
  "blindspot",
]);

// Scored edges from intervention → layer prune below this weight. Keeps the
// intv→friction / intv→harm / intv→suffering rings from becoming hairballs
// while still surfacing the dominant bottlenecks / relief pathways.
export const LAYER_EDGE_MIN_SCORE = 0.3;

export interface BuildGraphDataInput {
  camps: CampInput[];
  claims: ClaimInput[];
  interventions: InterventionInput[];
  sources: SourceInput[];
  evidence: EvidenceInput[];
  frictionLayers: LayerInput[];
  harmLayers: LayerInput[];
  sufferingLayers: LayerInput[];
  bridges: BridgeInput[];
  convergences: ConvergenceInput[];
  blindspots: BlindspotInput[];
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
    case "bridge":
      return `/bridges/${id}/`;
    case "convergence":
      return `/convergences/${id}/`;
    case "blindspot":
      return `/blindspots/${id}/`;
  }
}

function emojiFor(kind: NodeKind, id: string): string {
  if (kind === "camp") return CAMP_EMOJI[id] ?? KIND_EMOJI.camp;
  return KIND_EMOJI[kind];
}

const STANCE_EDGE: Record<
  EvidenceInput["stance"],
  "stance_support" | "stance_contradict" | "stance_qualify"
> = {
  support: "stance_support",
  contradict: "stance_contradict",
  qualify: "stance_qualify",
};

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
  for (const s of input.sources) addNode(s.id, "source", s.title);
  for (const e of input.evidence) {
    // Evidence label: the stance + locator is more informative than the id.
    const label = e.locator
      ? `${e.stance}: ${e.locator}`
      : `${e.stance} · ${e.source_id}`;
    addNode(e.id, "evidence", label);
  }
  for (const l of input.frictionLayers) addNode(l.id, "friction_layer", l.name);
  for (const l of input.harmLayers) addNode(l.id, "harm_layer", l.name);
  for (const l of input.sufferingLayers)
    addNode(l.id, "suffering_layer", l.name);
  for (const b of input.bridges) {
    addNode(b.id, "bridge", `${b.from_camp} → ${b.to_camp}`);
  }
  for (const c of input.convergences) {
    addNode(
      c.id,
      "convergence",
      `${c.camps.length}-camp ⇒ ${c.intervention_id}`,
    );
  }
  for (const b of input.blindspots) {
    addNode(b.id, "blindspot", `${b.against_prior_set} · ${b.flagged_camp_id}`);
  }

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

  for (const e of input.evidence) {
    addEdge(e.id, e.source_id, "cites_source");
    addEdge(e.id, e.claim_id, STANCE_EDGE[e.stance]);
  }

  for (const iv of input.interventions) {
    for (const [layerId, score] of Object.entries(iv.friction_scores)) {
      if (score >= LAYER_EDGE_MIN_SCORE) {
        addEdge(iv.id, layerId, "scores_friction");
      }
    }
    for (const [layerId, score] of Object.entries(iv.harm_scores)) {
      if (score >= LAYER_EDGE_MIN_SCORE) {
        addEdge(iv.id, layerId, "scores_harm");
      }
    }
    for (const [layerId, score] of Object.entries(
      iv.suffering_reduction_scores,
    )) {
      if (score >= LAYER_EDGE_MIN_SCORE) {
        addEdge(iv.id, layerId, "relieves_suffering");
      }
    }
  }

  for (const b of input.bridges) {
    addEdge(b.id, b.from_camp, "bridge_from");
    addEdge(b.id, b.to_camp, "bridge_to");
  }

  for (const c of input.convergences) {
    addEdge(c.id, c.intervention_id, "converges_on");
    for (const campId of c.camps) {
      addEdge(c.id, campId, "converges_camp");
    }
    for (const normId of Object.values(c.divergent_reasons)) {
      addEdge(c.id, normId, "converges_via_norm");
    }
  }

  for (const b of input.blindspots) {
    addEdge(b.id, b.flagged_camp_id, "flags_camp");
  }

  return { nodes, edges };
}

// Astro-land loader. Reads every content collection + the latest leverage
// coalition set. Falls back gracefully if no leverage analysis exists yet
// (graph renders nodes + structural edges but without coalition edges).
export async function loadGraphData(): Promise<GraphData> {
  const [
    camps,
    desc,
    norm,
    interventions,
    sources,
    evidence,
    frictionLayers,
    harmLayers,
    sufferingLayers,
    bridges,
    convergences,
    blindspots,
  ] = await Promise.all([
    getCollection("camps"),
    getCollection("descriptiveClaims"),
    getCollection("normativeClaims"),
    getCollection("interventions"),
    getCollection("sources"),
    getCollection("evidence"),
    getCollection("frictionLayers"),
    getCollection("harmLayers"),
    getCollection("sufferingLayers"),
    getCollection("bridges"),
    getCollection("convergences"),
    getCollection("blindspots"),
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
      friction_scores: i.data.friction_scores,
      harm_scores: i.data.harm_scores,
      suffering_reduction_scores: i.data.suffering_reduction_scores,
    })),
    sources: sources.map((s) => ({ id: s.data.id, title: s.data.title })),
    evidence: evidence.map((e) => ({
      id: e.data.id,
      claim_id: e.data.claim_id.id,
      source_id: e.data.source_id.id,
      stance: e.data.supports,
      locator: e.data.locator ?? "",
    })),
    frictionLayers: frictionLayers.map((l) => ({
      id: l.data.id,
      name: l.data.name,
    })),
    harmLayers: harmLayers.map((l) => ({ id: l.data.id, name: l.data.name })),
    sufferingLayers: sufferingLayers.map((l) => ({
      id: l.data.id,
      name: l.data.name,
    })),
    bridges: bridges.map((b) => ({
      id: b.data.id,
      from_camp: b.data.from_camp.id,
      to_camp: b.data.to_camp.id,
      translation: b.data.translation,
    })),
    convergences: convergences.map((c) => ({
      id: c.data.id,
      intervention_id: c.data.intervention_id.id,
      camps: c.data.camps.map((r) => r.id),
      divergent_reasons: c.data.divergent_reasons,
    })),
    blindspots: blindspots.map((b) => ({
      id: b.data.id,
      flagged_camp_id: b.data.flagged_camp_id.id,
      against_prior_set: b.data.against_prior_set,
    })),
    coalitions: latest ? latest.analysis.coalition_analyses : [],
  });
}
