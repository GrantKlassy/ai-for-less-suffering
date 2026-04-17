// Shape of an analysis JSON emitted by the afls engine.
// Source of truth: engine/afls/queries/palantir.py (PalantirAnalysis).

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

export interface PalantirAnalysis {
  generated_at: string;
  camps: string[];
  descriptive_convergences: string[];
  convergent_interventions: ConvergentIntervention[];
  bridges: Bridge[];
  blindspots: BlindSpot[];
}

export interface AnalysisEntry {
  id: string;
  analysis: PalantirAnalysis;
}
