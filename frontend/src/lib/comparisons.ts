// Comparing countries (API_CONTRACT.md → Comparing countries; PRD §3.19; DECISIONS 98). Words
// only: every pair, difference, figure and grade comes from the backend.
import type { Grade, GradeKey } from "./grade";

export type PairStatus = "proposed" | "suggested" | "confirmed" | "only_reference" | "only_other";
export type DifferenceStatus = "open" | "kept" | "classed" | "dismissed";
export type ReasonClass = "required" | "chosen" | "inherited" | "unknown";
export type Topic = "decision_right" | "role_presence" | "role_reason" | "way_of_working";

export interface Candidate {
  engagement_id: string;
  name: string;
  country: string;
  process_name: string;
  why: string;
  published_version_id: string | null;
  published_label: string | null;
}

export interface Side {
  engagement_id: string;
  name: string;
  country: string;
  version_id: string;
  version_label: string;
  newer_version_label: string | null;
}

export interface ComparedStep {
  key: string;
  code: string;
  label: string;
  kind: string;
  lane: string;
  phase: string;
  order: number;
}

export interface Pair {
  reference_key: string | null;
  other_key: string | null;
  status: PairStatus;
  why: string;
}

export interface Difference {
  key: string;
  kind: string;
  topic: Topic | "";
  title: string;
  reference_value: string;
  other_value: string;
  figure: string;
  reference_key: string | null;
  other_key: string | null;
  status: DifferenceStatus;
  code: string | null;
  reason_class: ReasonClass | null;
  reason_note: string;
  note: string;
  grade: Grade;
  grade_reason: string;
}

export interface DifferenceCounts {
  open: number;
  kept: number;
  classed: number;
  dismissed: number;
}

export interface Comparison {
  id: string;
  rules_version: string;
  reference: Side;
  other: Side;
  same_process: string;
  steps: { reference: ComparedStep[]; other: ComparedStep[] };
  pairs: Pair[];
  differences: Difference[];
  no_longer_found: Difference[];
  counts: DifferenceCounts;
  suggest_job: { job_id: string; status: string } | null;
}

export interface ComparisonSummary {
  id: string;
  reference: Side;
  other: Side;
  differences: DifferenceCounts;
}

export type PairDecisionKind = "confirmed" | "only_reference" | "only_other" | "clear";

export interface DifferenceDecision {
  action: "class" | "keep" | "dismiss" | "reopen";
  reason_class?: ReasonClass;
  reason_note?: string;
  grade?: GradeKey | null;
  note?: string;
}

/** The words the Capability Compass uses for each reason (Eric's brief §3). */
export const REASON_LABELS: Record<ReasonClass, string> = {
  required: "Required",
  chosen: "Chosen",
  inherited: "Inherited",
  unknown: "Not known yet",
};

export const REASON_HELP: Record<ReasonClass, string> = {
  required: "regulation, a customer contract or the physical site",
  chosen: "a deliberate local decision someone can state",
  inherited: "history, an acquisition or habit; nobody decided it",
  unknown: "nobody has said yet",
};

export const TOPIC_LABELS: Record<Topic, string> = {
  decision_right: "Who decides",
  role_presence: "Which roles exist",
  role_reason: "Why a role is there",
  way_of_working: "How the work runs",
};

export const STATUS_LABELS: Record<DifferenceStatus, string> = {
  open: "Not classed yet",
  kept: "Kept",
  classed: "Classed",
  dismissed: "Dismissed",
};

export const PAIR_LABELS: Record<PairStatus, string> = {
  proposed: "Proposed",
  suggested: "Suggested by Claude",
  confirmed: "Confirmed",
  only_reference: "Only in one country",
  only_other: "Only in one country",
};

function joined(names: string[]): string {
  return names.length <= 1 ? (names[0] ?? "") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/**
 * For the return file on Exports (Eric, 2026-11-14): a country that is the reference in a
 * comparison reads where those differences go (the other country's file). Null when it is never
 * the reference.
 */
export function referenceNote(engagementId: string, list: ComparisonSummary[]): string | null {
  const mine = list.filter((c) => c.reference.engagement_id === engagementId);
  const first = mine[0];
  if (!first) return null;
  const me = first.reference.country || first.reference.name;
  const others = [...new Set(mine.map((c) => c.other.country || c.other.name))];
  const files =
    others.length === 1 ? `${others[0]}'s return file` : `${joined(others.map((o) => `${o}'s`))} return files`;
  const what = others.length === 1 ? "its comparison" : "its comparisons";
  return `${me} is the reference in ${what} with ${joined(others)}, so those differences are in ${files}.`;
}

/** A comparison of this country on another version than the one chosen on Exports (Eric, 2026-11-14). */
export interface VersionNote {
  /** "refresh": the comparison is on an older version; "elsewhere": on a newer one. */
  kind: "refresh" | "elsewhere";
  reference: string;
  label: string;
}

/**
 * The differences go with the version compared, so on Exports the return file card says when a
 * comparison where this engagement is the other country is not on the chosen version.
 */
export function versionNotes(engagementId: string, versionId: string, list: ComparisonSummary[]): VersionNote[] {
  return list
    .filter((c) => c.other.engagement_id === engagementId && c.other.version_id !== versionId)
    .map((c) => ({
      kind: c.other.newer_version_label ? "refresh" : "elsewhere",
      reference: c.reference.country || c.reference.name,
      label: c.other.version_label,
    }));
}
