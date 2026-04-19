import { describe, expect, it } from "vitest";

import {
  CAMP_EMOJI,
  analysesReferencing,
  campEmoji,
  collectionForId,
} from "./graph";

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
    expect(collectionForId("evi_foo_bar")).toBe("evidence");
  });

  it("returns null for unknown prefixes", () => {
    expect(collectionForId("unknown_prefix")).toBeNull();
    expect(collectionForId("")).toBeNull();
    expect(collectionForId("camp")).toBeNull();
  });

  it("dispatches the new coalition prefixes", () => {
    expect(collectionForId("bridge_eacc_xrisk_regulatory_capture")).toBe(
      "bridges",
    );
    expect(collectionForId("conv_mental_health_triage")).toBe("convergences");
    expect(collectionForId("blind_religious")).toBe("blindspots");
  });
});

describe("analysesReferencing", () => {
  it("C14: returns [] for an id no analysis could ever reference", () => {
    // Use a clearly-synthetic id. `analysesReferencing` looks for `"<id>"`
    // (quoted), so a substring-of-a-real-id should return nothing --- this
    // is the prefix-collision safety check the function comment promises.
    expect(analysesReferencing("camp_does_not_exist_xyz")).toEqual([]);
  });

  it("C14: rejects a raw prefix that is not itself a full id", () => {
    // `"camp_"` is a substring of every real camp id's serialized JSON, but
    // no id equals literally `camp_`. Because the function searches for a
    // quoted needle, nothing matches.
    expect(analysesReferencing("camp_")).toEqual([]);
    expect(analysesReferencing("desc_")).toEqual([]);
  });

  it("C14: resolves a real id that appears in the corpus", () => {
    // Load-bearing smoke: if this returns [], the corpus may have stopped
    // referencing camp_anthropic (unlikely --- it's central to the graph)
    // or `analysesReferencing` has lost its quote-aware search.
    const hits = analysesReferencing("camp_anthropic");
    expect(hits.length).toBeGreaterThan(0);
  });
});
