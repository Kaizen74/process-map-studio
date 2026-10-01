// Data shapes of the review workbench's tabs (API_CONTRACT.md → Draft: rejected claims, lint;
// Review: questions, merge proposals, audit). In lib so that components/tabs can type their props
// without importing src/api; api/types.ts re-exports them.

export interface RejectedClaim {
  id: string;
  claim_text: string;
  source_id: string;
  source_name: string;
  anchor: string;
  reason: string;
  guardrail: string;
  stage: string;
  passage_available: boolean;
  segment_id: string | null;
}

export interface RejectedClaims {
  items: RejectedClaim[];
  total: number;
  scrub_count: number;
  instruction_like_count: number;
}

export interface LintIssue {
  rule: string;
  element_id: string | null;
  message: string;
  /** v1.10 §3.12.11: "done" or "documented" for a view's own flow check; null for the whole map. */
  view?: "done" | "documented" | null;
}

export interface LintReport {
  failures: LintIssue[];
  warnings: LintIssue[];
}

export interface Question {
  id: string;
  element_id: string | null;
  element_label: string;
  phase_id: string | null;
  phase_name: string;
  question: string;
  reason: string;
  status: "open" | "answered" | string;
}

export interface MergeClaim {
  text: string;
  source_name: string;
  anchor: string;
  quote: string;
}

export interface MergeGroup {
  label: string;
  kind: string;
  lane_role_name: string;
  element_id: string | null;
  claims: MergeClaim[];
}

export type MergeDecision = "pending" | "accepted" | "rejected" | "split";

export interface MergeProposal {
  id: string;
  proposed_label: string;
  similarity: number;
  decision: MergeDecision | string;
  decided_at: string | null;
  element_id: string | null;
  groups: MergeGroup[];
}

export interface AuditEntry {
  id: string;
  at: string;
  actor: string;
  action: string;
  target_type: string;
  target_id: string;
  target_label: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
}

// Quality card, publish and versions (phase P7; API_CONTRACT.md → Versions, publish and exports).

export interface QualityCheck {
  id: string;
  name: string;
  status: "pass" | "fail" | "warning";
  hard: boolean;
  detail: string;
}

export interface QualityCard {
  checks: QualityCheck[];
  warnings: string[];
  all_green: boolean;
}

export interface PublishBlocker {
  type: string;
  id: string;
  element_id: string | null;
  message: string;
}

/** How much independent evidence a map rests on (P12): from the kinds of its sources. */
export interface SignalStrength {
  level: "strong" | "moderate" | "limited";
  label: string;
  score: number;
  detail: string;
}

export interface VersionSummary {
  id: string;
  engagement_id: string;
  label: string;
  state: "draft" | "published" | "superseded" | string;
  created_at: string;
  published_at: string | null;
  published_by: string | null;
  parent_version_id: string | null;
  /** From the sources the version was drafted from (P12). */
  signal?: SignalStrength | null;
}

export interface ChangeEntry {
  change: "confirmed" | "edited" | "rejected" | "added" | string;
  step: string;
  stable_key: string;
}

export interface VersionDetail extends VersionSummary {
  review: { reviewed: number; total: number };
  change_log: ChangeEntry[];
  quality_card: QualityCard | null;
}
