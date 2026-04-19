// Latest-leverage selection and binding-friction helpers. Pure where possible;
// the Astro-land wrapper delegates to allAnalyses() in graph.ts.

import { allAnalyses } from "./graph";
import type { Analysis, AnalysisEntry, LeverageAnalysis } from "./analysis";

export interface LatestLeverage {
  id: string;
  analysis: LeverageAnalysis;
}

// Pure: scans any array of AnalysisEntry-shaped records for the most recent
// leverage analysis. Sort key is string-lexicographic on ISO8601 `generated_at`;
// `.Z`-suffixed zulu stamps sort correctly that way. Tiebreak by id so two runs
// in the same second produce a stable winner.
export function latestLeverageFrom(
  entries: { id: string; analysis: Analysis }[],
): LatestLeverage | null {
  const leverage = entries.filter(
    (e): e is { id: string; analysis: LeverageAnalysis } =>
      e.analysis.kind === "leverage",
  );
  if (leverage.length === 0) return null;
  leverage.sort((a, b) => {
    if (b.analysis.generated_at !== a.analysis.generated_at) {
      return b.analysis.generated_at.localeCompare(a.analysis.generated_at);
    }
    return b.id.localeCompare(a.id);
  });
  return leverage[0];
}

export function latestLeverageAnalysis(): LatestLeverage | null {
  return latestLeverageFrom(allAnalyses() as AnalysisEntry[]);
}

// Argmin across a friction_scores map. Ties broken lexicographically by key so
// the chip shown on the home page is deterministic across rebuilds.
export function bindingFrictionLayer(
  scores: Record<string, number>,
): string | null {
  const keys = Object.keys(scores);
  if (keys.length === 0) return null;
  keys.sort();
  let winner = keys[0];
  for (const k of keys) {
    if (scores[k] < scores[winner]) winner = k;
  }
  return winner;
}
