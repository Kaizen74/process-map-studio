// Data shapes of the map (API_CONTRACT.md → Draft: graph, layout; Review). They live in lib so
// that presentational components (components/map, components/panel) can type their props without
// importing src/api; api/types.ts re-exports them for everything else.

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
  edges: { id: string; from: string; to: string; kind: string; label: string }[];
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
  gap_findings: Record<string, unknown>[];
}
