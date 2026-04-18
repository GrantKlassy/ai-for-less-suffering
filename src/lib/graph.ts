// Graph-level helpers for the content collections. One source of truth for:
//   - id → {href, label, kind}  (NodeRef renders through this)
//   - reverse lookups (camps holding a claim, warrants for a claim, etc.)
//   - analyses-citing-this-node, which scans public-output/analyses/*.json
//
// The id → collection dispatch is prefix-based, mirroring the engine's
// _ID_PREFIX map at engine/afls/cli.py.

import fs from "node:fs";
import path from "node:path";
import { getCollection, getEntry } from "astro:content";
import { parseAnalysis, type Analysis } from "./analysis";

export type NodeKind =
  | "camp"
  | "descriptive_claim"
  | "normative_claim"
  | "intervention"
  | "source"
  | "friction_layer"
  | "harm_layer"
  | "suffering_layer"
  | "warrant";

export type CollectionName =
  | "camps"
  | "descriptiveClaims"
  | "normativeClaims"
  | "interventions"
  | "sources"
  | "frictionLayers"
  | "harmLayers"
  | "sufferingLayers"
  | "warrants";

export interface ResolvedRef {
  href: string;
  label: string;
  kind: NodeKind;
}

const COLLECTION_BY_PREFIX: { prefix: string; collection: CollectionName }[] = [
  { prefix: "camp_", collection: "camps" },
  { prefix: "desc_", collection: "descriptiveClaims" },
  { prefix: "norm_", collection: "normativeClaims" },
  { prefix: "intv_", collection: "interventions" },
  { prefix: "src_", collection: "sources" },
  { prefix: "friction_", collection: "frictionLayers" },
  { prefix: "harm_", collection: "harmLayers" },
  { prefix: "suffering_", collection: "sufferingLayers" },
  { prefix: "war_", collection: "warrants" },
];

const HREF_BY_COLLECTION: Record<CollectionName, (id: string) => string> = {
  camps: (id) => `/camps/${id}/`,
  descriptiveClaims: (id) => `/claims/descriptive/${id}/`,
  normativeClaims: (id) => `/claims/normative/${id}/`,
  interventions: (id) => `/interventions/${id}/`,
  sources: (id) => `/sources/${id}/`,
  frictionLayers: (id) => `/layers/friction/${id}/`,
  harmLayers: (id) => `/layers/harm/${id}/`,
  sufferingLayers: (id) => `/layers/suffering/${id}/`,
  // Warrants are edges. No detail page; renders fall back to the edge summary.
  warrants: () => "",
};

const KIND_BY_COLLECTION: Record<CollectionName, NodeKind> = {
  camps: "camp",
  descriptiveClaims: "descriptive_claim",
  normativeClaims: "normative_claim",
  interventions: "intervention",
  sources: "source",
  frictionLayers: "friction_layer",
  harmLayers: "harm_layer",
  sufferingLayers: "suffering_layer",
  warrants: "warrant",
};

export function collectionForId(id: string): CollectionName | null {
  const match = COLLECTION_BY_PREFIX.find((p) => id.startsWith(p.prefix));
  return match?.collection ?? null;
}

// Presentation-only. Not part of the camp data model --- the engine's Pydantic
// schema forbids extra fields, and mixing presentation into data violates the
// layering rule. Every place a camp is rendered should apply this (either via
// resolveNode, which does it centrally, or via campEmoji for direct reads).
export const CAMP_EMOJI: Record<string, string> = {
  camp_anthropic: "🧡",
  camp_content_creators: "✍️",
  camp_displaced_workers: "👷",
  camp_eacc: "🚀",
  camp_environmentalists: "🌳",
  camp_openai: "🌀",
  camp_open_weights: "🔓",
  camp_operator: "🕺",
  camp_palantir: "💣",
  camp_regulators: "⚖️",
  camp_religious: "🛐",
  camp_xrisk: "📉",
};

export function campEmoji(id: string): string {
  return CAMP_EMOJI[id] ?? "";
}

function truncate(s: string, max = 80): string {
  return s.length <= max ? s : s.slice(0, max - 1).trimEnd() + "…";
}

function pickLabel(
  collection: CollectionName,
  data: Record<string, unknown>,
): string {
  if (collection === "sources" && typeof data.title === "string") {
    return data.title;
  }
  if (typeof data.name === "string" && data.name.length > 0) {
    return data.name;
  }
  if (typeof data.text === "string") {
    return truncate(data.text);
  }
  return typeof data.id === "string" ? data.id : "";
}

export async function resolveNode(id: string): Promise<ResolvedRef | null> {
  const collection = collectionForId(id);
  if (!collection) return null;
  const entry = await getEntry(collection, id);
  if (!entry) return null;
  const label = pickLabel(collection, entry.data as Record<string, unknown>);
  const emoji = collection === "camps" ? campEmoji(id) : "";
  return {
    href: HREF_BY_COLLECTION[collection](id),
    label: emoji ? `${emoji} ${label}` : label,
    kind: KIND_BY_COLLECTION[collection],
  };
}

// ---------------------------------------------------------------------------
// Reverse lookups. Each detail page surfaces at least one of these so the
// graph is traversable both directions.

export async function campsHoldingDescriptive(id: string) {
  const all = await getCollection("camps");
  return all.filter((c) =>
    c.data.held_descriptive.some((ref) => ref.id === id),
  );
}

export async function campsHoldingNormative(id: string) {
  const all = await getCollection("camps");
  return all.filter((c) => c.data.held_normative.some((ref) => ref.id === id));
}

export async function warrantsForClaim(id: string) {
  const all = await getCollection("warrants");
  return all.filter((w) => w.data.claim_id.id === id);
}

export async function warrantsFromSource(id: string) {
  const all = await getCollection("warrants");
  return all.filter((w) => w.data.source_id.id === id);
}

export async function interventionsScoringFriction(id: string) {
  const all = await getCollection("interventions");
  return all.filter((i) => id in i.data.friction_scores);
}

export async function interventionsScoringHarm(id: string) {
  const all = await getCollection("interventions");
  return all.filter((i) => id in i.data.harm_scores);
}

export async function interventionsScoringSuffering(id: string) {
  const all = await getCollection("interventions");
  return all.filter((i) => id in i.data.suffering_reduction_scores);
}

// ---------------------------------------------------------------------------
// Analyses aren't a content collection (they're emitted JSON with the `kind`
// discriminator reconstructed from filename prefix --- see src/lib/analysis.ts).
// We load them once at build time and scan the serialized JSON for references.

interface AnalysisEntry {
  id: string;
  analysis: Analysis;
}

let _analyses: AnalysisEntry[] | null = null;

function loadAllAnalyses(): AnalysisEntry[] {
  if (_analyses !== null) return _analyses;
  const dir = path.resolve(process.cwd(), "public-output/analyses");
  if (!fs.existsSync(dir)) {
    _analyses = [];
    return _analyses;
  }
  _analyses = fs
    .readdirSync(dir)
    .filter((n) => n.endsWith(".json"))
    .map((n) => {
      const id = n.replace(/\.json$/, "");
      const raw = fs.readFileSync(path.join(dir, n), "utf-8");
      return { id, analysis: parseAnalysis(n, raw) };
    });
  return _analyses;
}

// Returns analyses whose serialized JSON contains "id" as a quoted string.
// The surrounding double-quotes are what make this safe against prefix
// collisions (desc_accel vs desc_accelerating) --- an ID only appears quoted
// when it's serving as a string value in the JSON, never as a substring of
// a longer ID.
export function analysesReferencing(id: string): AnalysisEntry[] {
  const needle = `"${id}"`;
  return loadAllAnalyses().filter(({ analysis }) =>
    JSON.stringify(analysis).includes(needle),
  );
}

export function allAnalyses(): AnalysisEntry[] {
  return loadAllAnalyses();
}
