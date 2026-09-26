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

export type SourceKind =
  | "interview_transcript"
  | "sop"
  | "manual"
  | "job_description"
  | "executed_artefact"
  | "other";

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
export type StageStatus = "waiting" | "running" | "done" | "failed" | "later";

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
  type: "read_source" | "draft";
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
  verified: number;
  rejected: number;
  open_questions: number;
  scrubbed: number;
}

export interface DraftState {
  job: Job | null;
  version: Version | null;
  summary: DraftSummary | null;
}

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
