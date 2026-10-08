// System records (API_CONTRACT.md → System records: event logs, metrics, alignment, system trace;
// PRD §3.13; P10b R1-R6): the shapes the backend sends, for the screens built in R7 and R8, and the
// plain words they show. The backend works everything out; nothing here computes a figure.

export interface DroppedRows {
  unparseable_time: number;
  missing_case_or_activity: number;
  duplicate: number;
}

export interface ValidationReport {
  rows_read: number;
  rows_kept: number;
  cases: number;
  activities: number;
  date_from: string | null;
  date_to: string | null;
  dropped: DroppedRows;
  dropped_share: number;
  single_event_cases: number;
  unknown_role_events: number;
  outside_window: number;
  timestamp_format: string;
  missing_columns: string[];
  refused: boolean;
  refusal: string;
}

/** A user ID from a file still held in memory (never stored), with a suggested role. */
export interface ResourceRow {
  value: string;
  events: number;
  suggested_role_id: string | null;
}

export type LogStatus = "uploaded" | "mapped" | "imported" | "failed";

export interface EventLog {
  id: string;
  engagement_id: string;
  name: string;
  system: string;
  timezone: string;
  window_start: string | null;
  window_end: string | null;
  status: LogStatus;
  column_map: Record<string, string | null>;
  timestamp_format: string | null;
  file_held: boolean;
  resources: ResourceRow[];
  role_map: Record<string, string | null>;
  validation_report: ValidationReport | null;
  approved_by_role: string;
  approved_at: string | null;
  created_at: string;
}

/** Median and 90th percentile, in minutes, over n values. */
export interface Spread {
  median_min: number;
  p90_min: number;
  n: number;
}

export type TimeBasis = "wait" | "not_separable";

export interface MonthVolume {
  month: string;
  events: number;
  cases: number;
}

export interface ActivityMetrics {
  activity: string;
  events: number;
  cases: number;
  cases_per_week: number;
  cases_per_month: number;
  months: MonthVolume[];
  months_too_few: number;
  work: Spread | null;
  wait_before: Spread | null;
  basis: TimeBasis;
  rework_cases: number;
  rework_share: number;
}

export interface TransitionMetrics {
  from_activity: string;
  to_activity: string;
  count: number;
  cases: number;
  elapsed: Spread;
  basis: TimeBasis;
  handoffs: number;
}

export interface CaseMetrics {
  cases: number;
  events: number;
  activities: number;
  date_from: string | null;
  date_to: string | null;
  weeks: number;
  cycle_time: Spread | null;
  basis: TimeBasis;
  rework_cases: number;
  rework_share: number;
  handoffs: number;
  handoffs_per_case: number;
  variants: number;
  exception_share: number;
}

export interface VariantMetrics {
  rank: number;
  activities: string[];
  cases: number;
  share: number;
  cumulative_share: number;
}

export interface RoleMetrics {
  role: string;
  events: number;
  cases: number;
  activities: string[];
  work: Spread | null;
}

export type MetricScope = "activity" | "transition" | "case" | "variant" | "role";

export interface MetricGroup<M> {
  scope: MetricScope;
  key: string;
  label: string;
  case_count: number;
  metrics: M;
}

/** Only groups of at least `minimum_cases` cases; `too_few` counts the rest (never shown). */
export interface MetricsResponse<M> {
  log_id: string;
  scope: MetricScope;
  minimum_cases: number;
  groups: MetricGroup<M>[];
  too_few: number;
}

export type AlignmentStatus = "proposed" | "confirmed" | "hidden_work" | "no_system_record";

export interface AlignmentRow {
  activity: string;
  element_id: string | null;
  element_label: string;
  status: AlignmentStatus;
  confirmed: boolean;
  proposed_by: "app" | "claude" | "eric";
  reason: string;
  events: number;
  cases: number;
}

export interface AlignmentSummary {
  activities: number;
  matched: number;
  hidden_work: number;
  no_system_record: number;
  waiting: number;
}

export interface Alignment {
  log_id: string;
  version_id: string;
  rows: AlignmentRow[];
  summary: AlignmentSummary;
}

export interface TraceActivity {
  activity: string;
  cases: number;
  events: number;
  work: Spread | null;
  wait_before: Spread | null;
  basis: TimeBasis;
}

/** One step's system-trace evidence from one log: figures, never a quote or a user ID. */
export interface SystemTrace {
  element_id: string;
  label: string;
  stance: "supports" | "contradicts";
  log_id: string;
  log_name: string;
  system: string;
  window_start: string | null;
  window_end: string | null;
  cases: number;
  events: number;
  cases_per_week: number;
  rework_cases: number;
  rework_share: number;
  activities: TraceActivity[];
  note: string;
}

/** "median 13.4 min · 90th percentile 26.6 min", or that there is nothing to show. */
export function spreadText(spread: Spread | null): string {
  if (!spread) return "No times recorded";
  return `median ${spread.median_min} min · 90th percentile ${spread.p90_min} min`;
}

/** §3.13.5: without end times the system can't tell working from waiting. */
export function basisText(basis: TimeBasis): string {
  return basis === "wait" ? "Work and wait" : "Working and waiting (not separable)";
}

export const ALIGNMENT_STATUS_LABELS: Readonly<Record<AlignmentStatus, string>> = {
  proposed: "Proposed match",
  confirmed: "Matched",
  hidden_work: "Hidden work (no step)",
  no_system_record: "No system record (offline)",
};

// --- The import wizard (R7a; API_CONTRACT.md → System records: event logs) ----------------------

export interface LogUpload {
  file: File;
  name: string;
  system: string;
  timezone: string;
  window_start: string;
  window_end: string;
}

export interface ColumnMapInput {
  columns: Record<string, string | null>;
  timestamp_format: string | null;
  timezone?: string;
}

export interface ImportInput {
  approved_by_role: string;
  confirm_approval: boolean;
}

export interface ImportStarted {
  job_id: string;
  log_id: string;
}

/** B.40 log columns, in the order the wizard lists them. */
export const LOG_FIELDS = [
  "case_id",
  "activity",
  "timestamp",
  "end_timestamp",
  "resource",
  "role",
  "system",
  "case_attribute",
] as const;
export type LogField = (typeof LOG_FIELDS)[number];

export const LOG_FIELD_LABELS: Record<LogField, string> = {
  case_id: "Case ID",
  activity: "Activity",
  timestamp: "Timestamp (start)",
  end_timestamp: "End timestamp",
  resource: "User ID (converted to a role, never stored)",
  role: "Role",
  system: "System",
  case_attribute: "Case detail (for example region or priority)",
};

export const REQUIRED_FIELDS: readonly LogField[] = ["case_id", "activity", "timestamp"];

/** The date formats the backend accepts as a correction (mining.FORMATS), with an example each. */
export const TIMESTAMP_FORMATS: readonly { value: string; example: string }[] = [
  { value: "%Y-%m-%dT%H:%M:%S", example: "2026-03-02T09:15:00" },
  { value: "%Y-%m-%d %H:%M:%S", example: "2026-03-02 09:15:00" },
  { value: "%Y-%m-%d %H:%M", example: "2026-03-02 09:15" },
  { value: "%Y-%m-%dT%H:%M", example: "2026-03-02T09:15" },
  { value: "%d/%m/%Y %H:%M:%S", example: "02/03/2026 09:15:00 (day first)" },
  { value: "%d/%m/%Y %H:%M", example: "02/03/2026 09:15 (day first)" },
  { value: "%m/%d/%Y %H:%M:%S", example: "03/02/2026 09:15:00 (month first)" },
  { value: "%m/%d/%Y %H:%M", example: "03/02/2026 09:15 (month first)" },
  { value: "%d.%m.%Y %H:%M:%S", example: "02.03.2026 09:15:00" },
  { value: "%d.%m.%Y %H:%M", example: "02.03.2026 09:15" },
  { value: "%d-%m-%Y %H:%M:%S", example: "02-03-2026 09:15:00" },
  { value: "%d-%m-%Y %H:%M", example: "02-03-2026 09:15" },
  { value: "ISO 8601 with offset", example: "2026-03-02T09:15:00+08:00" },
];

/** Time zones offered in the wizard; the backend accepts any IANA name. */
export const TIME_ZONES: readonly string[] = [
  "Asia/Singapore",
  "Asia/Kuala_Lumpur",
  "Asia/Hong_Kong",
  "Asia/Shanghai",
  "Asia/Tokyo",
  "Asia/Kolkata",
  "Asia/Dubai",
  "Australia/Sydney",
  "Pacific/Auckland",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "UTC",
];

export const LOG_STATUS_LABELS: Record<LogStatus, string> = {
  uploaded: "Uploaded: map the columns",
  mapped: "Columns mapped: ready to import",
  imported: "Imported",
  failed: "Import didn't finish: upload again",
};

/** The wizard's steps (PRD §5.4 System records). */
export const WIZARD_STEPS = ["Map columns", "Time zone", "Map users to roles", "Validation report", "Approve and import"] as const;
export type WizardStep = (typeof WIZARD_STEPS)[number];

/** The data request template Eric sends to IT (criterion 82; no engagement needed). */
export const DATA_REQUEST_FILES: readonly { format: "docx" | "md" | "csv"; label: string }[] = [
  { format: "docx", label: "Word" },
  { format: "md", label: "Markdown" },
  { format: "csv", label: "CSV header" },
];

export const dataRequestUrl = (format: "docx" | "md" | "csv") => `/api/templates/data-request?format=${format}`;
