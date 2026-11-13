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
  /** Optional module (R7, decision A): off until Eric switches it on. */
  system_records_enabled: boolean;
  /** Optional module (R10, decision A): on by default, as before. */
  gap_analysis_enabled: boolean;
  /** Optional module (R10, decision A): the value calculator and step dispositions; off by default. */
  value_enabled: boolean;
  reality_views_enabled: boolean;
  /** Settings → Regional (R10): an ISO 4217 code for the value calculator. */
  currency: string;
  /** Settings → Regional (R10): the time zone a new system log starts with. */
  default_timezone: string;
  /** Settings → AI spending (2026-10-19): the most one draft or refresh may cost; null for no limit. */
  draft_cost_limit_usd: number | null;
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

/** Codebook tier 2 settings Eric chooses per engagement (PRD Appendix E, §5.4 Setup; C7a). */
export interface MappingConventions {
  granularity: "coarse" | "standard" | "fine";
  label_style: "standard" | "sme";
  phase_naming: "sme" | "standard";
}

export const DEFAULT_CONVENTIONS: MappingConventions = { granularity: "standard", label_style: "standard", phase_naming: "sme" };

export interface ScopeFields {
  conventions?: MappingConventions;
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
  trigger_external?: boolean;
  end_point_external?: boolean;
  every_flow?: boolean;
  /** DECISIONS 98: the country it covers; refused for an engagement from a hand-off. */
  country?: string;
}

/** What an engagement keeps of the Capability Compass hand-off it started from (DECISIONS 95). */
export interface CompassLink {
  key: string;
  pilot_ref: string;
  cluster_ref: string;
  cluster_name: string;
  cell_refs: string[];
  /** Suggested probes for interview guides: never a claim, a step or a source. */
  interview_prompts: string[];
  ready: boolean;
  generated_at: string;
  /** The packet's engagement.country, as received (DECISIONS 98; absent before). */
  country?: string;
}

/** An engagement mapping the same pilot of the same frame in another country (DECISIONS 98). */
export interface SameProcess {
  engagement_id: string;
  name: string;
  country: string;
  process_name: string;
  has_published: boolean;
}

export interface HandoffPilot {
  ref: string;
  cluster_ref: string;
  cluster_name: string;
  name: string;
  process_name: string;
  process_kpi: string;
  industry: string;
  in_scope_roles: string[];
  interview_prompts: string[];
  cell_refs: string[];
  same_process?: SameProcess[];
}

/** POST /compass/preview: what a hand-off file would create; nothing is applied. */
export interface HandoffPreview {
  key: string;
  organisation: string;
  generated_at: string;
  ready: boolean;
  verdict: string;
  open: string[];
  pilots: HandoffPilot[];
  principles: { ref: string; text: string; refuted_by: string }[];
  country?: string;
}

/** POST /engagements: the scope fields plus, optionally, the hand-off and the lanes to create. */
export interface EngagementCreate extends ScopeFields {
  name: string;
  compass?: { handoff: unknown; pilot_ref: string };
  role_names?: string[];
  /** Another country's engagement to start from: its scope fields left out and conventions. */
  reference_engagement_id?: string;
}

/** POST /engagements/{id}/another-country (DECISIONS 98). */
export interface AnotherCountry {
  country: string;
  name?: string;
  role_ids?: string[] | null;
}

export type TestingVerdict = "open" | "supported" | "refuted";

/** What we are testing: a principle from the hand-off or a hypothesis Eric added. */
export interface TestingItem {
  id: string;
  ref: string;
  text: string;
  refuted_by: string;
  origin: "compass" | "owner";
  verdict: TestingVerdict;
  evidence_refs: string[];
  note: string;
}

export interface TestingPatch {
  verdict?: TestingVerdict;
  evidence_refs?: string[];
  note?: string;
  text?: string;
  refuted_by?: string;
}

/** POST /engagements/{id}/another-flow (DECISIONS 81): the next flow's own scope. */
export interface AnotherFlow {
  name: string;
  trigger: string;
  end_point: string;
  out_of_scope: string;
  /** The roles to bring along (DECISIONS 93); left out, every role comes along. */
  role_ids?: string[];
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
  /** Absent from engagements saved before C7a: the defaults apply. */
  conventions?: MappingConventions;
  /** E1: the process starts or ends outside the organisation (absent before E1: no). */
  trigger_external?: boolean;
  end_point_external?: boolean;
  /** DECISIONS 81: an overview of every flow in the documents (absent before: no, one flow). */
  every_flow?: boolean;
  /** The hand-off it started from, or null (absent before DECISIONS 95: none). */
  compass?: CompassLink | null;
  /** DECISIONS 98: the country it covers ("" when not known), and the engagement it started from. */
  country?: string;
  reference_engagement_id?: string | null;
  reference_engagement_name?: string;
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
  /** Not cited, but a claim or question set aside as another flow's cites it (DECISIONS 94). */
  other_flow?: boolean;
}

export interface SegmentPage {
  segments: Segment[];
  total: number;
  page: number;
  pages: number;
  coverage_pct: number | null;
  /** The source's passages tagged other_flow, across every page (DECISIONS 94). */
  other_flow?: number;
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
  origin: "speaker_map" | "email_header" | "manual" | string;
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
  type:
    | "read_source"
    | "draft"
    | "refresh"
    | "gap_internal"
    | "gap_external"
    | "interview_guide"
    | "event_log_import"
    | "event_log_alignment"
    | "intent_extract"
    | "intent_compare";
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
  /** DECISIONS 81: checked claims about another flow, set aside (absent before: 0). */
  outside_flow?: number;
  /** DECISIONS 83: the reading's questions about another flow, set aside (absent before: 0). */
  outside_flow_questions?: number;
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

/** What drafting now would probably cost (API_CONTRACT.md → GET …/draft/estimate). */
export interface DraftEstimate {
  sources: number;
  characters: number;
  input_tokens: number;
  output_tokens: number;
  /** null when the model has no price in the app's price list. */
  cost_usd: number | null;
  basis: "assumed" | "measured";
  drafts_measured: number;
  model: string;
  /** The day the price list was checked, "2026-10-19". */
  prices_checked_on: string;
  limit_usd: number | null;
  over_limit: boolean;
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
  OutsideFlowClaim,
  OutsideFlowClaims,
  OutsideFlowQuestion,
  PassageClaim,
  QualityCard,
  QualityCheck,
  PublishBlocker,
  NextStep,
  NextStepItem,
  NextSteps,
  AcceptedSteps,
  SignalStrength,
  VersionSummary,
  VersionDetail,
  ChangeEntry,
} from "../lib/reviewTypes";
