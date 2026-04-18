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
