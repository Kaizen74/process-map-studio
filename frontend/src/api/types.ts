import type { SourceKind } from "../lib/mapTypes";
import type { SignalStrength } from "../lib/reviewTypes";

// Response shapes, mirroring API_CONTRACT.md. Edit the contract first, then these.

export interface Health {
  status: string;
  app_version: string;
  prd_version: string;
}

export type EffortLevel = "low" | "medium" | "high" | "xhigh" | "max";

export interface Settings {
  owner_name: string;
  model: string;
  effort: EffortLevel | string;
  verifier_enabled: boolean;
  web_research_enabled: boolean;
  key_set: boolean;
  key_last4: string;
}

export interface WebSearchTest {
  available: boolean;
  message: string;
}

export interface ConnectionTest {
  key_valid: boolean;
  model_available: boolean;
  capabilities: { pdf_input: boolean; structured_outputs: boolean };
  message: string;
}

export interface ModelSummary {
  id: string;
  display_name: string;
  pdf_input: boolean;
  structured_outputs: boolean;
  effort_levels: string[];
}

export interface ModelChoices {
  models: ModelSummary[];
  from_anthropic: boolean;
  message: string;
}

export interface ModelUpdate {
  model: string;
  effort: string;
  verifier_enabled: boolean;
}

export interface ScopeFields {
  name?: string;
  process_name?: string;
  trigger?: string;
  end_point?: string;
  in_scope_roles?: string[];
  out_of_scope?: string;
  process_kpi?: string;
  industry?: string;
  adjacent_industries?: string[];
  confidential_terms?: string[];
}

export interface Engagement {
  id: string;
  name: string;
  process_name: string;
  trigger: string;
  end_point: string;
  in_scope_roles: string[];
  out_of_scope: string;
  process_kpi: string;
  industry: string;
  adjacent_industries: string[];
  confidential_terms: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

export interface EngagementSummary extends Engagement {
  latest_version: { label: string; state: string } | null;
  review_progress: { reviewed: number; total: number };
  sources_count: number;
}

export type NavKey =
  | "setup"
  | "interview"
  | "sources"
  | "draft"
  | "review"
  | "published"
  | "matrix"
  | "gap_analysis"
  | "registers"
  | "leadership"
  | "exports";

export type NavState = "done" | "attention" | "not_started";

export interface Readiness {
  key_set: boolean;
  transcripts_ready: boolean;
  documents_ready: boolean;
  speakers_unmapped: number;
  draft_exists: boolean;
  blockers_count: number;
  nav: Record<NavKey, NavState>;
  nav_counts: Partial<Record<NavKey, number>>;
  next_step: NavKey | null;
  missing: string[];
  /** What would make the map stronger but doesn't stop the draft (P12). */
  recommended?: string[];
  signal?: SignalStrength | null;
  ready_to_draft: boolean;
}

export interface Role {
  id: string;
  engagement_id: string;
  name: string;
  aliases: string[];
  is_system: boolean;
  lane_order: number | null;
}

export interface RoleCreate {
  name: string;
  aliases?: string[];
  is_system?: boolean;
}

export type RolePatch = Partial<Pick<Role, "name" | "aliases" | "is_system">> & { lane_order?: number };

export interface Source {
  id: string;
  engagement_id: string;
  kind: SourceKind | string;
  filename: string;
  format: string;
  mime: string;
  version_date: string;
  owner: string;
  controlled_copy: boolean;
  text_status: "pending" | "ready" | "failed" | string;
  error: string;
  segment_count: number;
  ocr_pages: number[];
  suggested_images: number;
  created_at: string;
  /** G11 (P9): the share of its passages the current map cites; null before a draft uses it. */
  coverage_pct?: number | null;
  /** Only on upload (and kind changes that re-read the file): the background reading job. */
  job_id?: string | null;
}

export interface SourcePatch {
  kind?: string;
  version_date?: string;
  owner?: string;
  controlled_copy?: boolean;
}

export interface SourceUpload {
  file: File;
  kind?: string;
}

export interface Segment {
  id: string;
  seq: number;
  anchor: string;
  page: number | null;
  section: string;
  speaker_role: string | null;
  text: string;
  cited: boolean;
  instruction_like: boolean;
  /** Only with raw=1 (owner-only correction editor). */
  speaker_label?: string | null;
  corrected?: boolean;
  /** Interviews: the guide question this turn asks or answers (§3.12.10 step A), once drafted. */
  question_id?: string | null;
}

export interface SegmentPage {
  segments: Segment[];
  total: number;
  page: number;
  pages: number;
  coverage_pct: number | null;
}

export interface Speaker {
  label: string;
  segment_count: number;
  role_id: string | null;
  is_interviewer: boolean;
}

/** For each speaker label: a role ID, "interviewer", or null to clear. */
export type SpeakerMapping = Record<string, string | null>;

export interface RedactionTerm {
  id: string;
  engagement_id: string;
  term: string;
  replacement: string;
  origin: "speaker_map" | "manual" | string;
}

// --- Jobs and drafting (API_CONTRACT.md → Jobs, Draft) — phase P3 ---------------------------

export type JobStatus = "queued" | "running" | "done" | "failed";
export type StageStatus = "waiting" | "running" | "done" | "failed" | "skipped" | "later";

export interface JobStage {
  id: string;
  name: string;
  status: StageStatus;
  started_at: string | null;
  finished_at: string | null;
}

export interface Job {
  id: string;
  engagement_id: string | null;
  type: "read_source" | "draft" | "refresh" | "gap_internal" | "gap_external" | "interview_guide";
  target_id: string | null;
  status: JobStatus;
  stage: string;
  progress: number;
  message: string;
  error: string;
  usage: { calls: number; input_tokens: number; output_tokens: number } | null;
  claims: { verified: number; rejected: number };
  stages: JobStage[];
  created_at: string;
}

export interface Version {
  id: string;
  engagement_id: string;
  label: string;
  state: "draft" | "published" | "superseded";
  created_at: string;
}

export interface DraftSummary {
  steps: number;
  needs_check: number;
  verified: number;
  rejected: number;
  open_questions: number;
  scrubbed: number;
}

/** How a draft or refresh was made (API_CONTRACT.md → Run record). */
export interface RunRecord {
  model: string;
  effort: string | null;
  verifier: boolean;
  instructions: Record<string, string>;
  app_version: string;
}

/** What a refresh would do differently from the run that made the draft (warn, never block). */
export interface RefreshCheck {
  made_with: RunRecord | null;
  now: RunRecord;
  changes: string[];
}

/** What a refresh changed among the steps not yet reviewed (API_CONTRACT.md → refresh). */
export interface RefreshChanges {
  kept: number;
  new_steps: string[];
  no_longer_drafted: string[];
  renamed: { before: string; after: string }[];
}

export interface DraftState {
  job: Job | null;
  version: Version | null;
  summary: DraftSummary | null;
  last_refresh?: RefreshChanges | null;
}

export interface AiUsageRow {
  id: string;
  created_at: string;
  job_id: string | null;
  stage_id: string;
  prompt_version: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  duration_ms: number;
  status: "ok" | "error" | "mock";
}

export interface AiUsage {
  items: AiUsageRow[];
  totals: { calls: number; input_tokens: number; output_tokens: number };
}

// --- The map as a graph (API_CONTRACT.md → Draft: graph, lint) — phase P4 ------------------

// Map, layout and panel shapes live in lib (components may import lib, not api).
export type {
  SourceKind,
  GraphEvidence,
  GraphElement,
  Graph,
  Align,
  TextPos,
  NodeShape,
  LayoutNode,
  Point,
  LayoutEdge,
  Layout,
  EvidenceCard,
  RaciDetail,
  ElementDetail,
} from "../lib/mapTypes";
export type {
  AuditEntry,
  LintIssue,
  LintReport,
  MergeClaim,
  MergeGroup,
  MergeProposal,
  MergeDecision,
  Question,
  RejectedClaim,
  RejectedClaims,
  QualityCard,
  QualityCheck,
  PublishBlocker,
  SignalStrength,
  VersionSummary,
  VersionDetail,
  ChangeEntry,
} from "../lib/reviewTypes";
