// Data shapes of the map (API_CONTRACT.md → Draft: graph, layout; Review). They live in lib so
// that presentational components (components/map, components/panel) can type their props without
// importing src/api; api/types.ts re-exports them for everything else.

import type { StepGapFinding } from "./gap";

export type SourceKind =
  | "interview_transcript"
  | "sop"
  | "manual"
  | "job_description"
  | "executed_artefact"
  | "other";

// The map as a graph (phase P4).

export interface GraphEvidence {
  segment_id: string | null;
  source_id: string;
  source_kind: SourceKind;
  stance: "supports" | "contradicts" | "silent";
  anchor: string;
  verified: boolean;
  note: string;
}

export interface GraphElement {
  id: string;
  stable_key: string;
  kind: "activity" | "decision" | "approval" | "start" | "end";
  label: string;
  lane_role_id: string | null;
  phase_id: string | null;
  time: { work_min: number | null; wait_min: number | null; text: string };
  complexity: "L" | "M" | "H" | null;
  kpi: string;
  decision: { mechanism: string; decider_role_id: string | null; rule_or_threshold: string; escalation: string };
  handoff: { in: string; out: string };
  raci: { role_id: string; letter: "R" | "A" | "C" | "I"; contested: boolean }[];
  provenance: "O" | "I" | "R";
  r_reference: string;
  source_state: string;
  divergence_types: string[];
  constraints: { text: string; provenance: string; cause_type: string | null; is_key: boolean }[];
  k_risk: string;
  ai_flag: { component: string; input: string; output: string; handoff: string; basis: string } | null;
  evidence: GraphEvidence[];
  confidence: number | null;
  confidence_breakdown: { label: string; delta: number }[];
  needs_check: boolean;
  review_status: string;
  /** v1.10 §3.12.3: the accounts the step's interview claims give. */
  account_summary?: { official: number; lived: number; unclear: number };
  /** false = "Practice not described" (only the official account); null = interview silent. */
  practice_described?: boolean | null;
  /** v1.10 §3.12.11: where practice and the documents differ, both values. */
  variants?: { done?: Record<string, string>; documented?: Record<string, string> } | null;
  /** v1.10 §3.12.11 (B.35); null on maps drafted before v1.10. */
  view_membership?: ViewMembership | null;
}

export type ViewMembership = "both" | "done_only" | "documented_only";
export type SequenceBasis = "explicit_order" | "document_order" | "dependency" | "narration_order";

export interface GraphEdge {
  id: string;
  from: string;
  to: string;
  /** B.8; "gap" is a "not described" connector (As done only). */
  kind: string;
  label: string;
  /** v1.10 §3.12.10 (B.34): why the line is there; null on lines Eric added. */
  sequence_basis?: SequenceBasis | null;
  view_membership?: ViewMembership | null;
  information_payload?: string | null;
  typical?: boolean | null;
}

export interface Graph {
  version: { id: string; label: string; state: string; quality_card: Record<string, unknown> | null };
  process: {
    name: string;
    trigger: string;
    end_point: string;
    kpi: string;
    cycle_time: { elapsed_min: number; work_min: number; incomplete_steps: number };
  };
  roles: { id: string; name: string; is_system: boolean; lane_order: number | null }[];
  phases: { id: string; name: string; time_window: string; order: number }[];
  elements: GraphElement[];
  edges: GraphEdge[];
}

// Layout and the detail panel (phase P5).

export type Align = "left" | "center" | "right";

export interface TextPos {
  x: number;
  y: number;
  align: Align;
}

export type NodeShape = "rounded_rect" | "pill" | "diamond" | "circle" | "double_circle";

export interface LayoutNode {
  id: string;
  shape: NodeShape;
  x: number;
  y: number;
  w: number;
  h: number;
  label_lines: string[];
  label_pos: TextPos;
  lens_pos: TextPos;
}

export type Point = [number, number];

export interface LayoutEdge {
  id: string;
  kind: string;
  is_back_edge: boolean;
  points: Point[];
  label: string;
  label_pos: TextPos | null;
}

export interface Layout {
  canvas: { w: number; h: number };
  lanes: { role_id: string; label: string; step_count: number; y: number; h: number }[];
  phases: { phase_id: string; label: string; time_window: string; x: number; w: number }[];
  nodes: LayoutNode[];
  edges: LayoutEdge[];
}

export interface EvidenceCard {
  segment_id: string | null;
  source_id: string;
  source_name: string;
  source_kind: SourceKind;
  stance: "supports" | "contradicts" | "silent";
  anchor: string;
  verified: boolean;
  quote: string;
  note: string;
}

export interface RaciDetail {
  role_id: string;
  role_name: string;
  letter: "R" | "A" | "C" | "I";
  contested: boolean;
  sources: { source_name: string; source_kind: SourceKind; anchor: string }[];
}

export interface ElementDetail extends Omit<GraphElement, "evidence" | "raci"> {
  version_id: string;
  lane_role_name: string;
  phase_name: string;
  decider_role_name: string;
  evidence: EvidenceCard[];
  raci: RaciDetail[];
  image_count: number;
  gap_findings: StepGapFinding[];
  /** v1.10 §3.12.10 rule 6: the interview answers behind the step, with their guide questions. */
  answers?: AnswerQuote[];
}

/** One interview answer behind a step (API_CONTRACT.md → GET /api/elements/{eid}). */
export interface AnswerQuote {
  quote: string;
  account_type: "official" | "lived" | "unclear";
  account_cue: string;
  stated_reason: string;
  variation_condition: string;
  source_id: string;
  segment_id: string | null;
  anchor: string;
  question_id: string | null;
  question: string;
}
