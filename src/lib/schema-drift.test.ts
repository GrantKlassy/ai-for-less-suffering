// Schema-drift parity across the Python engine and the TypeScript site.
//
// Reads engine/tests/_enums.json (written by engine/tests/test_schema_drift.py)
// and asserts the maps in this package mirror the Python source of truth.
// The JSON is gitignored; `task check` always runs engine tests before site
// tests, so inside CI / pre-push it is present. If it is missing (developer
// ran vitest standalone), the suite throws with a pointer to the prerequisite
// instead of a confusing parse error.

import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { KIND_EMOJI, type NodeKind } from "./graph";
import { LAYER_EDGE_MIN_SCORE } from "./graph-data";
import { LEGEND, NODE_KIND_COLOR } from "./legend";

const ENUMS_JSON_PATH = path.resolve(
  __dirname,
  "../../engine/tests/_enums.json",
);

interface EnumsDump {
  SourceKind: string[];
  MethodTag: string[];
  Support: string[];
  InterventionKind: string[];
  ProvenanceMethod: string[];
  ID_PREFIX: Record<string, string>;
  NodeKinds: string[];
  LAYER_EDGE_MIN_SCORE: number;
}

function loadEnums(): EnumsDump {
  if (!fs.existsSync(ENUMS_JSON_PATH)) {
    throw new Error(
      `engine/tests/_enums.json missing. Run \`task engine:test\` first ` +
        `(or \`task check\`, which runs engine tests before site tests).`,
    );
  }
  return JSON.parse(fs.readFileSync(ENUMS_JSON_PATH, "utf-8")) as EnumsDump;
}

// Python kind → TS collection name. The drift test for D6 asserts Python and
// TS agree on prefix per collection; this translation is the crosswalk.
const KIND_TO_COLLECTION: Record<string, string> = {
  camp: "camps",
  descriptive_claim: "descriptiveClaims",
  normative_claim: "normativeClaims",
  intervention: "interventions",
  source: "sources",
  evidence: "evidence",
  friction_layer: "frictionLayers",
  harm_layer: "harmLayers",
  suffering_layer: "sufferingLayers",
  bridge: "bridges",
  convergence: "convergences",
  blindspot: "blindspots",
};

// Minimal Tailwind-palette hex table. Only the shades actually referenced by
// legend `classes` are included --- the D7 test parses `text-<c>-<n>` and
// `bg-<c>-<n>` out of the class string and looks the resulting color up here.
// Bumping a shade requires a one-line addition; the drift test will fail
// loudly if a class uses a shade missing from this table.
const TAILWIND_HEX: Record<string, Record<string, string>> = {
  zinc: { "300": "#d4d4d8", "500": "#71717a", "800": "#27272a" },
  sky: { "300": "#7dd3fc", "950": "#082f49" },
  violet: { "300": "#c4b5fd", "950": "#2e1065" },
  emerald: { "300": "#6ee7b7", "950": "#022c22" },
  amber: { "300": "#fcd34d", "950": "#451a03" },
  orange: { "300": "#fdba74", "950": "#431407" },
  rose: { "300": "#fda4af", "950": "#4c0519" },
  cyan: { "300": "#67e8f9", "950": "#083344" },
  lime: { "300": "#bef264", "950": "#1a2e05" },
  pink: { "300": "#f9a8d4", "950": "#500724" },
};

describe("schema drift: Python ↔ TypeScript parity", () => {
  const enums = loadEnums();

  it("D1: SourceKind matches Python", () => {
    // Mirror of the Zod enum in content.config.ts. Inlined because Zod
    // does not expose an introspectable options list.
    const ts = [
      "paper",
      "dataset",
      "filing",
      "press",
      "primary_doc",
      "blog",
      "dashboard",
    ].sort();
    expect(ts).toEqual(enums.SourceKind);
  });

  it("D2: MethodTag matches Python", () => {
    const ts = [
      "direct_measurement",
      "expert_estimate",
      "triangulation",
      "journalistic_report",
      "primary_testimony",
      "modeled_projection",
      "leaked_document",
    ].sort();
    expect(ts).toEqual(enums.MethodTag);
  });

  it("D3: Support (evidenceStance) matches Python", () => {
    const ts = ["support", "contradict", "qualify"].sort();
    expect(ts).toEqual(enums.Support);
  });

  it("D4: InterventionKind matches Python", () => {
    const ts = ["technical", "political", "economic"].sort();
    expect(ts).toEqual(enums.InterventionKind);
  });

  it("D5: ProvenanceMethod matches Python", () => {
    const ts = ["httpx", "manual_paste"].sort();
    expect(ts).toEqual(enums.ProvenanceMethod);
  });

  it("D6: _ID_PREFIX mirrors COLLECTION_BY_PREFIX", () => {
    // Extract `{ prefix: "foo_", collection: "bar" }` pairs from graph.ts.
    // Reading the source avoids exporting a private map just for the test.
    const graphSrc = fs.readFileSync(
      path.resolve(__dirname, "./graph.ts"),
      "utf-8",
    );
    const pattern =
      /\{\s*prefix:\s*"([^"]+)_",\s*collection:\s*"([^"]+)"\s*\}/g;
    const tsByCollection: Record<string, string> = {};
    for (const match of graphSrc.matchAll(pattern)) {
      const prefix = match[1];
      const collection = match[2];
      tsByCollection[collection] = prefix;
    }

    const pyByCollection: Record<string, string> = {};
    for (const [kind, prefix] of Object.entries(enums.ID_PREFIX)) {
      const collection = KIND_TO_COLLECTION[kind];
      expect(
        collection,
        `no TS collection for Python kind ${kind}`,
      ).toBeTruthy();
      pyByCollection[collection] = prefix;
    }

    expect(tsByCollection).toEqual(pyByCollection);
  });

  it("D7: NODE_KIND_COLOR hex matches Tailwind classes in LEGEND", () => {
    // Parse `text-<color>-<shade>` and `bg-<color>-<shade>` tokens out of the
    // legend pill's class string, look up the expected hex in TAILWIND_HEX,
    // and assert it matches the entry in NODE_KIND_COLOR. Catches the case
    // where a pill is re-colored without updating the graph fill (which
    // reads NODE_KIND_COLOR) or vice versa.
    for (const entry of LEGEND) {
      const textMatch = entry.classes.match(/text-(\w+)-(\d+)/);
      const bgMatch = entry.classes.match(/bg-(\w+)-(\d+)/);
      expect(textMatch, `no text-<c>-<n> in ${entry.classes}`).toBeTruthy();
      expect(bgMatch, `no bg-<c>-<n> in ${entry.classes}`).toBeTruthy();

      const [, textColor, textShade] = textMatch!;
      const [, bgColor, bgShade] = bgMatch!;
      const expectedFill = TAILWIND_HEX[textColor]?.[textShade];
      const expectedBg = TAILWIND_HEX[bgColor]?.[bgShade];
      expect(
        expectedFill,
        `${textColor}-${textShade} missing from TAILWIND_HEX`,
      ).toBeTruthy();
      expect(
        expectedBg,
        `${bgColor}-${bgShade} missing from TAILWIND_HEX`,
      ).toBeTruthy();

      const got = NODE_KIND_COLOR[entry.kind];
      expect(got.fill, `fill drift for ${entry.kind}`).toBe(expectedFill);
      expect(got.bg, `bg drift for ${entry.kind}`).toBe(expectedBg);
    }
  });

  it("D8a: every Python NodeKind has a TS NodeKind", () => {
    const tsKinds = Object.keys(KIND_EMOJI) as NodeKind[];
    expect(tsKinds.sort()).toEqual([...enums.NodeKinds].sort());
  });

  it("D8b: every Python NodeKind has a legend entry", () => {
    const legendKinds = new Set(LEGEND.map((e) => e.kind));
    for (const kind of enums.NodeKinds) {
      expect(
        legendKinds.has(kind as NodeKind),
        `legend missing entry for ${kind}`,
      ).toBe(true);
    }
  });

  it("D8c: every Python NodeKind has a NODE_KIND_COLOR entry", () => {
    for (const kind of enums.NodeKinds) {
      expect(
        NODE_KIND_COLOR[kind as NodeKind],
        `NODE_KIND_COLOR missing ${kind}`,
      ).toBeDefined();
    }
  });

  it("D9: LAYER_EDGE_MIN_SCORE matches the engine's pruning threshold", () => {
    // Both the CLI's layer-score lint and the homepage's edge-pruner key off
    // this number. If they diverge, the operator gets warnings about edges
    // the site still draws (or no warning about edges the site drops).
    expect(LAYER_EDGE_MIN_SCORE).toBe(enums.LAYER_EDGE_MIN_SCORE);
  });
});
