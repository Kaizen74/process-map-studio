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
