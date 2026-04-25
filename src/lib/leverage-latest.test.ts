import { describe, expect, it } from "vitest";

import type { Analysis, LeverageAnalysis } from "./analysis";
import { bindingFrictionLayer, latestLeverageFrom } from "./leverage-latest";

function lev(generated_at: string): LeverageAnalysis {
  return {
    kind: "leverage",
    generated_at,
    camps: [],
    descriptive_convergences: [],
    rankings: [],
    coalition_analyses: [],
    ranking_blindspots: [],
    contested_claims: [],
  };
}

describe("latestLeverageFrom", () => {
  it("picks the analysis with the largest generated_at", () => {
    const entries = [
      {
        id: "leverage_20260417T170908Z",
        analysis: lev("2026-04-17T17:09:08Z"),
      },
      {
        id: "leverage_20260418T221002Z",
        analysis: lev("2026-04-18T22:10:02Z"),
      },
      {
        id: "leverage_20260410T000000Z",
        analysis: lev("2026-04-10T00:00:00Z"),
      },
    ];
    expect(latestLeverageFrom(entries)?.id).toBe("leverage_20260418T221002Z");
  });

  it("returns null when there are no leverage entries", () => {
    const coalition: Analysis = {
      kind: "coalition",
      generated_at: "2026-04-18T00:00:00Z",
      camps: [],
      descriptive_convergences: [],
      convergent_interventions: [],
      bridges: [],
      blindspots: [],
      contested_claims: [],
    };
    expect(
      latestLeverageFrom([{ id: "coalition_1", analysis: coalition }]),
    ).toBeNull();
  });

  it("tiebreaks by id descending when generated_at ties", () => {
    const entries = [
      { id: "leverage_aaa", analysis: lev("2026-04-18T22:10:02Z") },
      { id: "leverage_zzz", analysis: lev("2026-04-18T22:10:02Z") },
    ];
    expect(latestLeverageFrom(entries)?.id).toBe("leverage_zzz");
  });

  it("ignores non-leverage analyses entirely", () => {
    const coalition: Analysis = {
      kind: "coalition",
      generated_at: "2026-05-01T00:00:00Z",
      camps: [],
      descriptive_convergences: [],
      convergent_interventions: [],
      bridges: [],
      blindspots: [],
      contested_claims: [],
    };
    const entries = [
      { id: "coalition_new", analysis: coalition },
      { id: "leverage_older", analysis: lev("2026-04-18T22:10:02Z") },
    ];
    expect(latestLeverageFrom(entries)?.id).toBe("leverage_older");
  });
});

describe("bindingFrictionLayer", () => {
  it("returns the min-scoring friction layer id", () => {
    expect(
      bindingFrictionLayer({
        friction_regulation: 0.4,
        friction_grid: 0.9,
        friction_capex: 0.55,
      }),
    ).toBe("friction_regulation");
  });

  it("tiebreaks lexicographically by key", () => {
    expect(
      bindingFrictionLayer({
        friction_b: 0.3,
        friction_a: 0.3,
        friction_c: 0.9,
      }),
    ).toBe("friction_a");
  });

  it("returns null on empty map", () => {
    expect(bindingFrictionLayer({})).toBeNull();
  });
});
