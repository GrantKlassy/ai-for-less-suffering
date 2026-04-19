// Astro content collections. Each YAML kind in `data/` gets a collection.
// Cross-document links use `reference('<collection>')` so dangling IDs fail
// the build --- that's the point. Enum/field shapes mirror the Python schema
// at engine/afls/schema/. When the engine changes, this file changes.

import { defineCollection, reference, z } from "astro:content";
import { glob } from "astro/loaders";

const isoTime = z.string();
const nullableUrl = z.string().nullable();

// engine/afls/schema/evidence.py :: Support
const evidenceStance = z.enum(["support", "contradict", "qualify"]);

// engine/afls/schema/evidence.py :: MethodTag
const methodTag = z.enum([
  "direct_measurement",
  "expert_estimate",
  "triangulation",
  "journalistic_report",
  "primary_testimony",
  "modeled_projection",
  "leaked_document",
]);

// engine/afls/schema/interventions.py :: InterventionKind
const interventionKind = z.enum(["technical", "political", "economic"]);

// engine/afls/schema/sources.py :: SourceKind
const sourceKind = z.enum([
  "paper",
  "dataset",
  "filing",
  "press",
  "primary_doc",
  "blog",
  "dashboard",
]);

// engine/afls/schema/sources.py :: Provenance. Optional on Source because pre-
// provenance sources exist and will never be retroactively stamped.
const provenance = z.object({
  method: z.enum(["httpx", "manual_paste"]),
  tool: z.string().min(1),
  git_sha: z.string().min(1),
  at: isoTime,
  raw_content_hash: z.string().nullable().default(null),
});

const frictionLayers = defineCollection({
  loader: glob({ pattern: "**/*.yaml", base: "./data/friction_layers" }),
  schema: z.object({
    id: z.string(),
    kind: z.literal("friction_layer"),
    name: z.string().min(1),
    description: z.string().default(""),
    created_at: isoTime,
    updated_at: isoTime,
    provenance_url: nullableUrl,
  }),
});

const harmLayers = defineCollection({
  loader: glob({ pattern: "**/*.yaml", base: "./data/harm_layers" }),
  schema: z.object({
    id: z.string(),
    kind: z.literal("harm_layer"),
    name: z.string().min(1),
    description: z.string().default(""),
    created_at: isoTime,
    updated_at: isoTime,
    provenance_url: nullableUrl,
  }),
});

const sufferingLayers = defineCollection({
  loader: glob({ pattern: "**/*.yaml", base: "./data/suffering_layers" }),
  schema: z.object({
    id: z.string(),
    kind: z.literal("suffering_layer"),
    name: z.string().min(1),
    description: z.string().default(""),
    created_at: isoTime,
    updated_at: isoTime,
    provenance_url: nullableUrl,
  }),
});

const sources = defineCollection({
  loader: glob({ pattern: "**/*.yaml", base: "./data/sources" }),
  schema: z.object({
    id: z.string(),
    kind: z.literal("source"),
    source_kind: sourceKind,
    title: z.string().min(1),
    url: z.string().default(""),
    authors: z.array(z.string()).default([]),
    published_at: z.string().default(""),
    accessed_at: z.string().default(""),
    reliability: z.number().min(0).max(1),
    notes: z.string().default(""),
    provenance: provenance.nullable().default(null),
    created_at: isoTime,
    updated_at: isoTime,
    provenance_url: nullableUrl,
  }),
});

const descriptiveClaims = defineCollection({
  loader: glob({ pattern: "**/*.yaml", base: "./data/claims/descriptive" }),
  schema: z.object({
    id: z.string(),
    kind: z.literal("descriptive_claim"),
    text: z.string().min(1),
    confidence: z.number().min(0).max(1),
    created_at: isoTime,
    updated_at: isoTime,
    provenance_url: nullableUrl,
  }),
});

const normativeClaims = defineCollection({
  loader: glob({ pattern: "**/*.yaml", base: "./data/claims/normative" }),
  schema: z.object({
    id: z.string(),
    kind: z.literal("normative_claim"),
    text: z.string().min(1),
    created_at: isoTime,
    updated_at: isoTime,
    provenance_url: nullableUrl,
  }),
});

// Evidence currently only points at descriptive claims (verified by grep over
// data/evidence/). If a piece of evidence ever needs to point at a normative
// claim, this schema will fail the build and force the call to be made explicit.
const evidence = defineCollection({
  loader: glob({ pattern: "**/*.yaml", base: "./data/evidence" }),
  schema: z.object({
    id: z.string(),
    kind: z.literal("evidence"),
    claim_id: reference("descriptiveClaims"),
    source_id: reference("sources"),
    supports: evidenceStance,
    weight: z.number().min(0).max(1),
    method_tag: methodTag,
    locator: z.string().default(""),
    quote: z.string().default(""),
    created_at: isoTime,
    updated_at: isoTime,
    provenance_url: nullableUrl,
  }),
});

const camps = defineCollection({
  loader: glob({ pattern: "**/*.yaml", base: "./data/camps" }),
  schema: z.object({
    id: z.string(),
    kind: z.literal("camp"),
    name: z.string().min(1),
    summary: z.string().default(""),
    agents: z.array(z.string()).default([]),
    held_descriptive: z.array(reference("descriptiveClaims")).default([]),
    held_normative: z.array(reference("normativeClaims")).default([]),
    disputed_evidence: z.array(reference("evidence")).default([]),
    created_at: isoTime,
    updated_at: isoTime,
    provenance_url: nullableUrl,
  }),
});

// Operator-position ledger. Descriptive/normative wall: `data/priors/` holds the
// operator's stance on each intervention and does not go in `data/interventions/`.
// Keys on the `positions` record are intervention IDs; the same typegen carve-out
// as interventions.friction_scores applies (plain-string keys, referential
// integrity handled at engine-layer, not by `reference()`).
const operatorPositionFlip = z.object({
  ref: z.string(),
  direction: z.enum(["rises", "falls"]),
  note: z.string().default(""),
});

const operatorPositionEntry = z.object({
  stance: z.enum([
    "priority",
    "qualified_support",
    "skeptical",
    "oppose",
    "under_consideration",
  ]),
  prose: z.string().default(""),
  flip_conditions: z.array(operatorPositionFlip).default([]),
  updated_at: isoTime,
});

const operatorPositions = defineCollection({
  loader: glob({ pattern: "*.yaml", base: "./data/priors" }),
  schema: z.object({
    kind: z.literal("operator_positions"),
    operator: z.string().min(1),
    positions: z.record(z.string(), operatorPositionEntry),
  }),
});

const interventions = defineCollection({
  loader: glob({ pattern: "**/*.yaml", base: "./data/interventions" }),
  schema: z.object({
    id: z.string(),
    kind: z.literal("intervention"),
    text: z.string().min(1),
    action_kind: interventionKind,
    cost_estimate: z.string().default(""),
    leverage_score: z.number().min(0).max(1),
    // Keys are friction/harm layer IDs. Astro's typegen chokes when
    // reference() is used as a record key (it infers the value type as the
    // reference entry itself), so we keep keys as plain strings. Referential
    // integrity is already enforced by `afls validate` at engine-layer.
    friction_scores: z.record(z.string(), z.number().min(0).max(1)).default({}),
    harm_scores: z.record(z.string(), z.number().min(0).max(1)).default({}),
    suffering_reduction_scores: z
      .record(z.string(), z.number().min(0).max(1))
      .default({}),
    created_at: isoTime,
    updated_at: isoTime,
    provenance_url: nullableUrl,
  }),
});

export const collections = {
  frictionLayers,
  harmLayers,
  sufferingLayers,
  sources,
  descriptiveClaims,
  normativeClaims,
  evidence,
  camps,
  interventions,
  operatorPositions,
};
