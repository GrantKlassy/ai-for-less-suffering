// Shape of the analyses emitted by the afls engine.
// Sources of truth:
//   engine/afls/queries/coalition.py (CoalitionAnalysis)
//   engine/afls/queries/leverage.py (LeverageAnalysis)
//   engine/afls/queries/reallocation.py (ReallocationAnalysis)
//   engine/afls/queries/steelman.py (SteelmanAnalysis)
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

export interface EvidenceSummary {
  evidence_id: string;
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
  supports: EvidenceSummary[];
  contradicts: EvidenceSummary[];
  qualifies: EvidenceSummary[];
}

export interface CoalitionAnalysis {
  kind: "coalition";
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
  mean_harm_robustness: number;
  mean_suffering_reduction: number;
  composite_score: number;
  suffering_composite: number;
  net_composite: number;
  friction_scores: Record<string, number>;
  harm_scores: Record<string, number>;
  suffering_reduction_scores: Record<string, number>;
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

export interface ReallocationPair {
  from_intervention_id: string;
  to_intervention_id: string;
  from_net_composite: number;
  to_net_composite: number;
  delta_net: number;
  delta_suffering_composite: number;
  delta_harm_robustness: number;
  delta_viability: number;
}

export interface ReallocationCoalitionShift {
  from_intervention_id: string;
  to_intervention_id: string;
  gaining_camps: string[];
  losing_camps: string[];
  friction_rebinds: string;
}

export interface ReallocationBlindSpot {
  flagged_from_intervention_id: string;
  flagged_to_intervention_id: string;
  reasoning: string;
}

export interface ReallocationAnalysis {
  kind: "reallocation";
  generated_at: string;
  camps: string[];
  descriptive_convergences: string[];
  rankings: LeverageRanking[];
  pairs: ReallocationPair[];
  harm_divergence_flags: ReallocationPair[];
  coalition_shifts: ReallocationCoalitionShift[];
  reallocation_blindspots: ReallocationBlindSpot[];
  contested_claims: ContestedClaim[];
}

export interface SteelmanFrame {
  camp_id: string;
  normative_claim_ids: string[];
  descriptive_claim_ids: string[];
  case: string;
}

export interface SteelmanAnalysis {
  kind: "steelman";
  generated_at: string;
  target_intervention_id: string;
  target_intervention_text: string;
  case_for: SteelmanFrame[];
  case_against: SteelmanFrame[];
  conceded_descriptive: string[];
  contested_claims: ContestedClaim[];
  operator_tension: string;
}

export type Analysis =
  | CoalitionAnalysis
  | LeverageAnalysis
  | ReallocationAnalysis
  | SteelmanAnalysis;

export interface AnalysisEntry {
  id: string;
  analysis: Analysis;
}

// Filename prefix is the discriminator --- `coalition_<stamp>.json`,
// `leverage_<stamp>.json`, `reallocation_<stamp>.json`, or
// `steelman_<stamp>.json`. Throws on unknown prefix rather than silently
// falling back, so a new analysis kind can't ship without the renderer
// learning about it.
export function parseAnalysis(filename: string, raw: string): Analysis {
  const payload = JSON.parse(raw) as Record<string, unknown>;
  if (filename.startsWith("coalition_")) {
    return {
      kind: "coalition",
      ...(payload as Omit<CoalitionAnalysis, "kind">),
    };
  }
  if (filename.startsWith("leverage_")) {
    return { kind: "leverage", ...(payload as Omit<LeverageAnalysis, "kind">) };
  }
  if (filename.startsWith("reallocation_")) {
    return {
      kind: "reallocation",
      ...(payload as Omit<ReallocationAnalysis, "kind">),
    };
  }
  if (filename.startsWith("steelman_")) {
    return { kind: "steelman", ...(payload as Omit<SteelmanAnalysis, "kind">) };
  }
  throw new Error(`unknown analysis filename prefix: ${filename}`);
}
