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
  /** v1.10 §3.12.4 (C2): the kind of work, with the quoted cues that show it. */
  work_type?: WorkType | null;
  constraint_type?: "rigid" | "governing" | "enabling" | "absent" | null;
  work_type_basis?: { segment_ids: string[]; quote: string }[];
  work_type_status?: "proposed" | "confirmed" | "not_classified" | null;
  /** §3.12.10 rule 9 (K2): landscape · practice, and the landscape activity a practice step is
   * part of; null on a map with one level. */
  level?: "landscape" | "practice" | null;
  parent_element_id?: string | null;
}

export type WorkType = "clear" | "complicated" | "complex" | "chaotic" | "confused" | "not_classified";
/** The work types Eric can choose (V3b); "not classified" is the model's answer, not a choice. */
export type ChoosableWorkType = Exclude<WorkType, "not_classified">;
export const CHOOSABLE_WORK_TYPES: readonly ChoosableWorkType[] = ["clear", "complicated", "complex", "chaotic", "confused"];

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
  /** "I" for a line the translation added for one view (drawn per view from V1). */
  provenance?: "O" | "I" | "R";
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
  /** v1.10 §3.12.11: only in the other view (drawn ghosted with Show the other view). */
  ghost?: boolean;
}

export type Point = [number, number];

export interface LayoutEdge {
  id: string;
  kind: string;
  is_back_edge: boolean;
  points: Point[];
  label: string;
  label_pos: TextPos | null;
  ghost?: boolean;
}

export interface Layout {
  /** "done" · "documented" · null (the combined map). */
  view?: "done" | "documented" | null;
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
  /** v1.10 §3.12.6 (C2b): the ASHEN profile of a decision, approval or complex step. */
  know_how?: KnowHow | null;
  /** v1.10 §3.12.2 (C2b): the stories the SME told about the step, in their own words. */
  stories?: StoryCard[];
  /** V3 (§5.7.7 4a): the work type's quoted cues with their anchors. */
  work_type_cues?: { quote: string; source_id: string; segment_id: string | null; anchor: string }[];
}

export type AshenCategory = "artefacts" | "skills" | "heuristics" | "experience" | "natural_talent";

export interface AshenItem {
  text: string;
  quote: string;
  role: string;
  source_id: string;
  segment_id: string | null;
  anchor: string;
}

export interface KnowHow {
  kdp_type: "decision" | "judgment";
  ashen: Record<AshenCategory, AshenItem[]>;
  knowledge_risk: "high" | "medium" | "low" | "unknown";
  risk_reason: string;
  cadence: string | null;
  received: string[];
  attended: string[];
  wanted: string[];
  communicated_via: string[];
}

export interface StoryCard {
  label: string;
  fragment_type: string;
  signifiers: string[];
  frequency: string;
  single_account: boolean;
  quote: string;
  source_id: string;
  segment_id: string | null;
  anchor: string;
}

/** API_CONTRACT.md → GET /api/versions/{vid}/capability-notes (Preserve · Improve). */
export interface CapabilityNote {
  kind: "strength" | "weakness";
  dimension: string;
  text: string;
  cause_type: string | null;
  steps: string[];
  quote: string;
  source_id: string;
  segment_id: string | null;
  anchor: string;
}

/** API_CONTRACT.md → GET /api/versions/{vid}/glossary. */
export interface GlossaryEntry {
  term: string;
  plain_meaning: string;
  steps: string[];
  source_id: string;
  segment_id: string | null;
  anchor: string;
}

/** One interview answer behind a step (API_CONTRACT.md → GET /api/elements/{eid}). */
export interface AnswerQuote {
  quote: string;
  account_type: "official" | "lived" | "unclear";
  account_cue: string;
  stated_reason: string;
  variation_condition: string;
  /** How often, in the SME's words (X1); "" when not stated. */
  frequency: string;
  source_id: string;
  segment_id: string | null;
  anchor: string;
  question_id: string | null;
  question: string;
}
