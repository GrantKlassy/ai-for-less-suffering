import { describe, expect, it } from "vitest";

import type { OperatorPosition } from "./positions";
import { orphanedInterventions, unresolvedFlipRefs } from "./positions";

function pos(overrides: Partial<OperatorPosition> = {}): OperatorPosition {
  return {
    stance: "under_consideration",
    prose: "",
    flip_conditions: [],
    updated_at: "2026-04-18T22:30:00Z",
    ...overrides,
  };
}

describe("orphanedInterventions", () => {
  it("flags interventions missing from the positions record", () => {
    const positions = {
      intv_compute: pos(),
      intv_grid: pos(),
    };
    const ids = ["intv_compute", "intv_grid", "intv_drug_discovery"];
    expect(orphanedInterventions(ids, positions)).toEqual([
      "intv_drug_discovery",
    ]);
  });

  it("returns an empty list when every intervention has a position", () => {
    const positions = { intv_compute: pos() };
    expect(orphanedInterventions(["intv_compute"], positions)).toEqual([]);
  });
});

describe("unresolvedFlipRefs", () => {
  it("flags flip refs with no known collection prefix", () => {
    const positions = {
      intv_compute: pos({
        flip_conditions: [
          { ref: "unknown_thing", direction: "rises", note: "" },
          { ref: "desc_grid_constraint", direction: "falls", note: "resolves" },
        ],
      }),
    };
    expect(unresolvedFlipRefs(positions)).toEqual([
      { interventionId: "intv_compute", ref: "unknown_thing" },
    ]);
  });

  it("returns empty list when all flip refs resolve", () => {
    const positions = {
      intv_grid: pos({
        flip_conditions: [
          { ref: "friction_regulation", direction: "falls", note: "" },
        ],
      }),
    };
    expect(unresolvedFlipRefs(positions)).toEqual([]);
  });
});
