// Operator positions ledger. Thin wrapper over the `operatorPositions` content
// collection that enforces one-file-per-operator (we ship one: grant.yaml).
//
// The operator lives in data/priors/, not data/interventions/, on purpose ---
// positions are operator stance, interventions are world-model. Mixing them
// breaks the descriptive/normative wall.

import { getCollection } from "astro:content";
import { collectionForId } from "./graph";

export type Stance =
  | "priority"
  | "qualified_support"
  | "skeptical"
  | "oppose"
  | "under_consideration";

export interface FlipCondition {
  ref: string;
  direction: "rises" | "falls";
  note: string;
}

export interface OperatorPosition {
  stance: Stance;
  prose: string;
  flip_conditions: FlipCondition[];
  updated_at: string;
}

export interface OperatorPositions {
  operator: string;
  positions: Record<string, OperatorPosition>;
}

// Loads the single operator-position file. Throws if none exist or more than
// one is present --- a silent fallback here would mean the homepage renders
// without any operator stance and nobody notices.
export async function loadOperatorPositions(): Promise<OperatorPositions> {
  const entries = await getCollection("operatorPositions");
  if (entries.length === 0) {
    throw new Error(
      "no operator-position file found under data/priors/ --- expected grant.yaml",
    );
  }
  if (entries.length > 1) {
    throw new Error(
      `expected exactly one operator-position file, found ${entries.length}`,
    );
  }
  const entry = entries[0];
  return {
    operator: entry.data.operator,
    positions: entry.data.positions,
  };
}

// Pure: interventions that have no entry in the positions map. Shown as a
// build-time warning so an unstaged intervention doesn't silently render
// nothing on the home ledger.
export function orphanedInterventions(
  interventionIds: readonly string[],
  positions: Record<string, OperatorPosition>,
): string[] {
  return interventionIds.filter((id) => !(id in positions));
}

// Pure: flip_conditions whose `ref` doesn't resolve to any known collection.
// Run at build time and warn; don't hard-fail (the engine-layer validator is
// where the hard fail lives, not this presentation helper).
export function unresolvedFlipRefs(
  positions: Record<string, OperatorPosition>,
): { interventionId: string; ref: string }[] {
  const out: { interventionId: string; ref: string }[] = [];
  for (const [intvId, pos] of Object.entries(positions)) {
    for (const flip of pos.flip_conditions) {
      if (collectionForId(flip.ref) === null) {
        out.push({ interventionId: intvId, ref: flip.ref });
      }
    }
  }
  return out;
}
