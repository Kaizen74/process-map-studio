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
