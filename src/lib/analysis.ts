// Shape of the analyses emitted by the afls engine.
// Sources of truth:
//   engine/afls/queries/palantir.py (PalantirAnalysis)
//   engine/afls/queries/leverage.py (LeverageAnalysis)
//
// The `kind` discriminator is not serialized into the JSON payload (it is a
// Python ClassVar). It is reconstructed at load time from the filename prefix.

export interface ConvergentIntervention {
  intervention_id: string;
  supporting_camps: string[];
  divergent_reasons: Record<string, string>;
  operator_note: string;
}

export interface Bridge {
  id: string;
  kind: "bridge";
  from_camp: string;
  to_camp: string;
  translation: string;
  caveats: string[];
  created_at: string;
  updated_at: string;
  provenance_url: string | null;
}

export interface BlindSpot {
  id: string;
  kind: "blindspot";
  against_prior_set: string;
  flagged_camp_id: string;
  reasoning: string;
  created_at: string;
  updated_at: string;
  provenance_url: string | null;
}

export interface WarrantSummary {
  warrant_id: string;
  source_id: string;
  source_title: string;
  stance: "support" | "contradict" | "qualify";
  method_tag: string;
  weight: number;
  locator: string;
}

export interface ContestedClaim {
  claim_id: string;
  claim_text: string;
  supports: WarrantSummary[];
  contradicts: WarrantSummary[];
  qualifies: WarrantSummary[];
}

export interface PalantirAnalysis {
  kind: "palantir";
  generated_at: string;
  camps: string[];
  descriptive_convergences: string[];
  convergent_interventions: ConvergentIntervention[];
  bridges: Bridge[];
  blindspots: BlindSpot[];
  contested_claims: ContestedClaim[];
}

export interface LeverageRanking {
  intervention_id: string;
  intervention_text: string;
  leverage_score: number;
  mean_robustness: number;
  composite_score: number;
  friction_scores: Record<string, number>;
}

export interface InterventionCoalitionAnalysis {
  intervention_id: string;
  supporting_camps: string[];
  contesting_camps: string[];
  expected_friction: string;
}

export interface RankingBlindSpot {
  flagged_intervention_id: string;
  reasoning: string;
}

export interface LeverageAnalysis {
  kind: "leverage";
  generated_at: string;
  camps: string[];
  descriptive_convergences: string[];
  rankings: LeverageRanking[];
  coalition_analyses: InterventionCoalitionAnalysis[];
  ranking_blindspots: RankingBlindSpot[];
  contested_claims: ContestedClaim[];
}

export type Analysis = PalantirAnalysis | LeverageAnalysis;

export interface AnalysisEntry {
  id: string;
  analysis: Analysis;
}

// Filename prefix is the discriminator --- `palantir_<stamp>.json` vs
// `leverage_<stamp>.json`. Throws on unknown prefix rather than silently
// falling back, so a third analysis kind can't ship without the renderer
// learning about it.
export function parseAnalysis(filename: string, raw: string): Analysis {
  const payload = JSON.parse(raw) as Record<string, unknown>;
  if (filename.startsWith("palantir_")) {
    return { kind: "palantir", ...(payload as Omit<PalantirAnalysis, "kind">) };
  }
  if (filename.startsWith("leverage_")) {
    return { kind: "leverage", ...(payload as Omit<LeverageAnalysis, "kind">) };
  }
  throw new Error(`unknown analysis filename prefix: ${filename}`);
}
