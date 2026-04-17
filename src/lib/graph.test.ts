import { describe, expect, it } from "vitest";

import { CAMP_EMOJI, campEmoji, collectionForId } from "./graph";

describe("campEmoji", () => {
  it("returns the mapped emoji for a known camp", () => {
    expect(campEmoji("camp_eacc")).toBe("🚀");
    expect(campEmoji("camp_anthropic")).toBe("🧡");
    expect(campEmoji("camp_xrisk")).toBe("📉");
  });

  it("returns empty string for an unknown id (silent fallback)", () => {
    // This fallback is why the cross-layer drift check in
    // engine/tests/test_layering.py exists --- without it, a missing entry
    // would render labelless without failing any check.
    expect(campEmoji("camp_nonexistent")).toBe("");
    expect(campEmoji("desc_anything")).toBe("");
    expect(campEmoji("")).toBe("");
  });

  it("has an emoji for every CAMP_EMOJI key it declares", () => {
    for (const id of Object.keys(CAMP_EMOJI)) {
      expect(campEmoji(id)).not.toBe("");
    }
  });
});

describe("collectionForId", () => {
  it("dispatches each prefix to the right collection", () => {
    expect(collectionForId("camp_eacc")).toBe("camps");
    expect(collectionForId("desc_ai_accelerating")).toBe("descriptiveClaims");
    expect(collectionForId("norm_religious_human_dignity")).toBe(
      "normativeClaims",
    );
    expect(collectionForId("intv_compute")).toBe("interventions");
    expect(collectionForId("src_andreessen_techno_optimist")).toBe("sources");
    expect(collectionForId("friction_grid")).toBe("frictionLayers");
    expect(collectionForId("harm_water")).toBe("harmLayers");
    expect(collectionForId("war_foo_bar")).toBe("warrants");
  });

  it("returns null for unknown prefixes", () => {
    expect(collectionForId("unknown_prefix")).toBeNull();
    expect(collectionForId("")).toBeNull();
    expect(collectionForId("camp")).toBeNull();
  });
});
