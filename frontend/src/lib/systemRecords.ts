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
