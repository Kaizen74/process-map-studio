// Map lenses and node markers (PRD §5.5). A lens changes only the one text line under each node;
// it never adds a marker, and never changes data, exports or the quality card. Markers are at
// most three per node: key constraint, has images and the unreviewed outline. Pure functions;
// components/map draws what they return.

import type { GraphElement, WorkType } from "./mapTypes";
import type { StanceOrState } from "./stateGlyph";
import { variantFor, type AsView } from "./views";

export type Lens = "plain" | "source_state" | "confidence" | "time" | "work_type";

export const LENSES: readonly { value: Lens; label: string }[] = [
  { value: "plain", label: "Plain" },
  { value: "source_state", label: "Source state" },
  { value: "confidence", label: "Confidence" },
  { value: "time", label: "Time" },
  { value: "work_type", label: "Work type" },
];

/** PRD §5.5 Work type lens: a glyph shape and a word for each kind of work (never colour alone). */
export const WORK_TYPE_LABELS: Readonly<Record<WorkType, string>> = {
  clear: "Clear",
  complicated: "Complicated",
  complex: "Complex",
  chaotic: "Chaotic",
  confused: "Confused",
  not_classified: "Not classified",
};

/** Where the lens choice is remembered in the browser (PRD §5.5). */
export const LENS_STORAGE_KEY = "pms.lens";
/** Below this, the confidence bar is coral and the value danger text (PRD §5.5). */
export const LOW_CONFIDENCE = 0.6;
/** Width of a full confidence bar, and of the longest time bars, in px. */
export const BAR_WIDTH = 46;

const TIMED = new Set(["activity", "approval"]);
const STEPS = new Set(["activity", "decision", "approval"]);
const STATES = new Set<string>([
  "corroborated",
  "documented_only",
  "practiced_only",
  "contested",
  "trace_contradicted",
  "not_assessed",
]);

export type LensLine =
  | { kind: "none" }
  | { kind: "text"; text: string; danger: boolean }
  | { kind: "state"; state: StanceOrState }
  | { kind: "confidence"; value: number; text: string; low: boolean; bar: number }
  | { kind: "time"; text: string; work: number; wait: number }
  | { kind: "work_type"; type: WorkType; label: string; proposed: boolean };

export function isLens(value: unknown): value is Lens {
  return LENSES.some((lens) => lens.value === value);
}

/** "~20 min", "~40 min + 15 wait", "15 min wait"; "" when no minutes are known. */
export function durationText(work: number | null, wait: number | null): string {
  if (work === null && wait === null) return "";
  if (wait === null || wait === 0) return `~${work ?? 0} min`;
  if (work === null || work === 0) return `${wait} min wait`;
  return `~${work} min + ${wait} wait`;
}

const NO_TIME: LensLine = { kind: "text", text: "No time stated", danger: true };

/**
 * The line under a node for a lens. `longest` is the most minutes (work + wait) of any step.
 * Where the views differ on the step (§3.12.11 variants), the Plain lens shows the active view's
 * time, else its owner.
 */
export function lensLine(element: GraphElement, lens: Lens, longest = 0, view: AsView = "done"): LensLine {
  if (!STEPS.has(element.kind)) return { kind: "none" };
  const { work_min: work, wait_min: wait } = element.time;
  const timed = TIMED.has(element.kind);
  switch (lens) {
    case "plain": {
      const variant = variantFor(element, view);
      if (variant.time) return { kind: "text", text: variant.time, danger: false };
      if (variant.owner) return { kind: "text", text: `Owner: ${variant.owner}`, danger: false };
      const text = durationText(work, wait);
      if (text) return { kind: "text", text, danger: false };
      return timed ? NO_TIME : { kind: "none" };
    }
    case "source_state": {
      const state = STATES.has(element.source_state) ? element.source_state : "not_assessed";
      return { kind: "state", state: state as StanceOrState };
    }
    case "confidence": {
      const value = element.confidence;
      if (value === null) return { kind: "none" };
      return {
        kind: "confidence",
        value,
        text: value.toFixed(2),
        low: value < LOW_CONFIDENCE,
        bar: Math.round(BAR_WIDTH * Math.min(1, Math.max(0, value))),
      };
    }
    case "time": {
      if (work === null && wait === null) return timed ? NO_TIME : { kind: "none" };
      const scale = longest > 0 ? BAR_WIDTH / longest : 0;
      return {
        kind: "time",
        text: `${work ?? 0} + ${wait ?? 0}`,
        work: Math.round((work ?? 0) * scale),
        wait: Math.round((wait ?? 0) * scale),
      };
    }
    case "work_type": {
      const type = element.work_type ?? "not_classified";
      return {
        kind: "work_type",
        type,
        label: WORK_TYPE_LABELS[type],
        proposed: element.work_type_status === "proposed",
      };
    }
  }
}

/** The most minutes (work + wait) of any step: the time lens scales its bars to this. */
export function longestStep(elements: readonly GraphElement[]): number {
  return Math.max(0, ...elements.map((e) => (e.time.work_min ?? 0) + (e.time.wait_min ?? 0)));
}

export type MarkerKind = "key_constraint" | "images" | "unreviewed";

/** The markers on a node, at most three (PRD §5.5 and constraint 17). Lenses never add one. */
export function markersFor(element: GraphElement, options: { hasImages: boolean }): MarkerKind[] {
  if (!STEPS.has(element.kind)) return [];
  const markers: MarkerKind[] = [];
  if (element.constraints.some((c) => c.is_key)) markers.push("key_constraint");
  if (options.hasImages) markers.push("images");
  if (element.review_status === "draft") markers.push("unreviewed");
  return markers;
}

const KIND_NAMES: Readonly<Record<string, string>> = {
  activity: "Activity",
  decision: "Decision",
  approval: "Approval",
  start: "Start",
  end: "End",
};

const REVIEW_NAMES: Readonly<Record<string, string>> = {
  draft: "unreviewed",
  confirmed: "confirmed",
  edited: "edited",
  added: "added",
  rejected: "rejected",
};

/** Spoken name of a node (PRD §5.10): "Kind, label, lane, source state, review status". */
export function nodeName(element: GraphElement, laneName: string): string {
  const kind = KIND_NAMES[element.kind] ?? element.kind;
  if (!STEPS.has(element.kind)) return `${kind}, ${element.label}`;
  const state = element.source_state.replaceAll("_", " ");
  const review = REVIEW_NAMES[element.review_status] ?? element.review_status;
  return [kind, element.label, laneName, state, review].filter(Boolean).join(", ");
}
