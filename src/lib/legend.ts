// Legend data for the homepage node-type key. One source of truth so the page
// renders it AND the test verifies it --- drift between the two is impossible
// by construction. Every NodeKind gets a legend entry; the test in
// legend.test.ts asserts this invariant and flags duplicates.
//
// Emojis are duplicated from graph.ts's KIND_EMOJI map deliberately: the
// structural test cross-checks they agree, so changing one without the other
// fails loudly.

import { KIND_EMOJI, type NodeKind } from "./graph";

export interface LegendEntry {
  letter: string;
  kind: NodeKind;
  emoji: string;
  label: string;
  blurb: string;
  classes: string;
}

// Hex mirrors of the `classes` Tailwind pairs above. Single source of truth so
// the cytoscape graph on the homepage and the legend pill style cannot drift.
// `fill` = the bright text-side color; `bg` = the dark pill background.
// Values are the default Tailwind palette hexes --- bumping these requires
// bumping the matching `classes` entry above (enforced by legend.test.ts).
export interface NodeKindColor {
  fill: string;
  bg: string;
}

export const NODE_KIND_COLOR: Record<NodeKind, NodeKindColor> = {
  camp: { fill: "#d4d4d8", bg: "#27272a" },
  descriptive_claim: { fill: "#7dd3fc", bg: "#082f49" },
  normative_claim: { fill: "#c4b5fd", bg: "#2e1065" },
  intervention: { fill: "#6ee7b7", bg: "#022c22" },
  source: { fill: "#fcd34d", bg: "#451a03" },
  friction_layer: { fill: "#fdba74", bg: "#431407" },
  harm_layer: { fill: "#fda4af", bg: "#4c0519" },
  suffering_layer: { fill: "#6ee7b7", bg: "#022c22" },
  evidence: { fill: "#71717a", bg: "#27272a" },
};

export const LEGEND: LegendEntry[] = [
  {
    letter: "P",
    kind: "camp",
    emoji: KIND_EMOJI.camp,
    label: "Camp",
    blurb: "Coherent cluster of held claims.",
    classes: "bg-zinc-800 text-zinc-300",
  },
  {
    letter: "CD",
    kind: "descriptive_claim",
    emoji: KIND_EMOJI.descriptive_claim,
    label: "Descriptive claim",
    blurb: "What is.",
    classes: "bg-sky-950 text-sky-300",
  },
  {
    letter: "CN",
    kind: "normative_claim",
    emoji: KIND_EMOJI.normative_claim,
    label: "Normative claim",
    blurb: "What should be.",
    classes: "bg-violet-950 text-violet-300",
  },
  {
    letter: "S",
    kind: "source",
    emoji: KIND_EMOJI.source,
    label: "Source",
    blurb: "A citable primary document.",
    classes: "bg-amber-950 text-amber-300",
  },
  {
    letter: "E",
    kind: "evidence",
    emoji: KIND_EMOJI.evidence,
    label: "Evidence",
    blurb: "A source's stance on a claim --- support, contradict, or qualify.",
    classes: "bg-zinc-800 text-zinc-500",
  },
  {
    letter: "I",
    kind: "intervention",
    emoji: KIND_EMOJI.intervention,
    label: "Intervention",
    blurb: "A proposed action.",
    classes: "bg-emerald-950 text-emerald-300",
  },
  {
    letter: "LF",
    kind: "friction_layer",
    emoji: KIND_EMOJI.friction_layer,
    label: "Friction layer",
    blurb: "What slows deployment.",
    classes: "bg-orange-950 text-orange-300",
  },
  {
    letter: "LH",
    kind: "harm_layer",
    emoji: KIND_EMOJI.harm_layer,
    label: "Harm layer",
    blurb: "A welfare harm to weigh.",
    classes: "bg-rose-950 text-rose-300",
  },
  {
    letter: "LS",
    kind: "suffering_layer",
    emoji: KIND_EMOJI.suffering_layer,
    label: "Suffering layer",
    blurb: "A category of first-person suffering the intervention relieves.",
    classes: "bg-emerald-950 text-emerald-300",
  },
];
