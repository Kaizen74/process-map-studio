// Gap analysis (PRD §3.11, §5.4; API_CONTRACT.md → Gap analysis): report shapes, plain labels and
// pure helpers. Advisory only: nothing here changes the map.

export type GapMode = "internal" | "external";
export type GapStatus =
  | "brief_draft"
  | "queued"
  | "running"
  | "draft_report"
  | "finalised"
  | "failed";
export type Severity = "high" | "medium" | "low";
export type Disposition =
  | "open"
  | "added_question"
  | "added_cause"
  | "added_step"
  | "dismissed";
export type Section = "fact" | "interpretation" | "recommendation";
/** B.32: a reality gap's class (§3.12.7), proposed only from an SME's stated reason. */
export type GapClass =
  | "effective_adaptation"
  | "risky_drift"
  | "obsolete_rule"
  | "unexplained";

export interface GapCounts {
  kept: number;
  rejected: number;
  open: number;
  needs_check: number;
}

export interface GapAnalysis {
  id: string;
  version_id: string;
  version_label: string;
  mode: GapMode;
  status: GapStatus;
  job_id: string | null;
  error: string;
  created_at: string;
  completed_at: string | null;
  finalised_at: string | null;
  notes: string[];
  counts: GapCounts;
}

export interface GapEvidence {
  side: "documents" | "practice" | "external";
  source_id: string;
  source_kind: string;
  source_name: string;
  stance: "supports" | "contradicts" | "silent";
  segment_id: string | null;
  anchor: string;
  quote: string;
  url: string;
  tier: string;
  page_age: string;
  citation_id: string;
}

export interface GapFinding {
  id: string;
  section: Section;
  finding_type: string;
  title: string;
  text: string;
  element_ids: string[];
  elements: { id: string; label: string }[];
  evidence: GapEvidence[];
  basis: string;
  provenance: "O" | "I" | "R" | "";
  severity: Severity | null;
  evidence_strength: "strong" | "weak" | "dated";
  comparison: "absent" | "different" | null;
  verification_status: "verified" | "rejected";
  rejection_guardrail: string;
  rejection_reason: string;
  verifier_verdict: "supported" | "partial" | "not_supported" | "not_run";
  needs_check: boolean;
  question: string;
  notes: string[];
  disposition: Disposition;
  disposition_note: string;
  created_item_ref: string;
  /** Reality gaps only (C4b): proposed while open, Eric's final class once decided. */
  gap_class: GapClass | null;
  stated_reason: string;
  cause_type: string | null;
}

export interface Brief {
  process_name: string;
  industry: string;
  adjacent_industries: string[];
  region: string;
  steps: string[];
  questions: string[];
  max_searches: number;
  allowed_domains: string[];
  blocked_domains: string[];
  recency_years: number;
}

export interface ScanHit {
  text: string;
  reason: string;
}

export interface BriefState {
  brief: Brief;
  text: string;
  confirmed: boolean;
  scan: { hits: ScanHit[] };
}

export interface GapSource {
  id: string;
  url: string;
  title: string;
  domain: string;
  page_age: string;
  tier: string;
  returned_in_results: boolean;
}

export interface GapReport {
  analysis: GapAnalysis;
  findings: GapFinding[];
  rejected: GapFinding[];
  questions: GapFinding[];
  sources: GapSource[];
  brief: BriefState | null;
  usage: { calls: number; input_tokens: number; output_tokens: number } | null;
  search_count: number;
}

export interface GapBriefView {
  analysis: GapAnalysis;
  brief: BriefState;
}

export interface GapStarted {
  analysis_id: string;
  job_id: string;
}

export interface GapStepChoice {
  kind: "activity" | "decision" | "approval";
  label: string;
  lane_role_id: string;
  after_element_id: string;
  mechanism: "rule_based" | "judgment";
}

export interface FindingDecision {
  disposition: Exclude<Disposition, "open">;
  note?: string;
  step?: GapStepChoice;
  gap_class?: GapClass;
}

/** A finding on a step's detail panel (GET /elements/{eid} gap_findings). */
export interface StepGapFinding {
  id: string;
  analysis_id: string;
  mode: GapMode;
  title: string;
  severity: Severity | null;
  disposition: Disposition;
}

export const MODE_LABELS: Readonly<Record<GapMode, string>> = {
  internal: "Documents vs practice",
  external: "External best practice",
};

export const STATUS_LABELS: Readonly<Record<GapStatus, string>> = {
  brief_draft: "Brief not run yet",
  queued: "Waiting to start",
  running: "Running",
  draft_report: "Draft report",
  finalised: "Finalised",
  failed: "Failed",
};

export const SEVERITY_LABELS: Readonly<Record<Severity, string>> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const DISPOSITION_LABELS: Readonly<Record<Disposition, string>> = {
  open: "Open",
  added_question: "Added as a question",
  added_cause: "Added to the cause library",
  added_step: "Added as a step",
  dismissed: "Dismissed",
};

export const SECTION_LABELS: Readonly<Record<Section, string>> = {
  fact: "Facts",
  interpretation: "Interpretation",
  recommendation: "Recommendation",
};

const TYPE_LABELS: Readonly<Record<string, string>> = {
  dead_control_candidate: "Control nobody may perform",
  undocumented_work: "Undocumented work",
  ownership_mismatch: "Different owner",
  threshold_gap: "Different threshold",
  sequence_gap: "Different order",
  trigger_gap: "Different trigger",
  exception_gap: "Different exception route",
  stale_documentation: "Outdated document",
  documentation_update: "Document update",
  known_adaptation: "Known adaptation",
  unknown_rule: "Rule not known in practice",
  disclosure_gap: "Account differs from the record",
  control_gap: "Control leaves no trace",
  constraint_mismatch: "Rule doesn't fit the work",
  missing_step: "Missing step",
  missing_control: "Missing control",
  sequence_difference: "Different order",
  decision_rights_difference: "Different decision rights",
  time_or_threshold_benchmark: "Time or threshold benchmark",
  kpi_practice: "KPI practice",
  technology_enabler: "Technology",
  other_difference: "Other difference",
};

export const GAP_CLASS_LABELS: Readonly<Record<GapClass, string>> = {
  effective_adaptation: "Effective adaptation (codify it)",
  risky_drift: "Risky drift (correct it)",
  obsolete_rule: "Obsolete rule (retire or rewrite it)",
  unexplained: "Unexplained (ask)",
};

/** "capacity_mismatch" → "Capacity mismatch". */
export function causeLabel(cause: string): string {
  const words = cause.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export const GUARDRAIL_LABELS: Readonly<Record<string, string>> = {
  G3: "passage not given or evidence missing",
  G4: "quote not found in the source",
  G5: "number or role not found",
  G10: "name block",
  GX1: "no source cited",
  GX2: "source not returned by the search",
  GX3: "claim not in the cited text",
  GAV: "the independent check didn't support it",
};

export const STRENGTH_LABELS: Readonly<
  Record<GapFinding["evidence_strength"], string>
> = {
  strong: "Strong evidence",
  weak: "Weak evidence (vendor or unknown sources only)",
  dated: "Dated sources",
};

export function typeLabel(type: string): string {
  return TYPE_LABELS[type] ?? type.replace(/_/g, " ");
}

export function tierLabel(tier: string): string {
  const words = tier.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Queued or running: the screen keeps checking the job. */
export function isRunning(analysis: GapAnalysis | undefined | null): boolean {
  return analysis?.status === "queued" || analysis?.status === "running";
}

export interface GapFilters {
  type: string;
  severity: Severity | "";
  strength: GapFinding["evidence_strength"] | "";
  disposition: Disposition | "";
}

export const NO_FILTERS: GapFilters = {
  type: "",
  severity: "",
  strength: "",
  disposition: "",
};

export function filterFindings(
  findings: readonly GapFinding[],
  f: GapFilters,
): GapFinding[] {
  return findings.filter(
    (x) =>
      (!f.type || x.finding_type === f.type) &&
      (!f.severity || x.severity === f.severity) &&
      (!f.strength || x.evidence_strength === f.strength) &&
      (!f.disposition || x.disposition === f.disposition),
  );
}

/** Findings in the report's sections (the server's order is kept within each). */
export function bySection(
  findings: readonly GapFinding[],
): { section: Section; findings: GapFinding[] }[] {
  const order: Section[] = ["fact", "interpretation", "recommendation"];
  return order
    .map((section) => ({
      section,
      findings: findings.filter((f) => f.section === section),
    }))
    .filter((group) => group.findings.length > 0);
}

/** "2 high · 1 medium" for the history list; "no findings" when there are none. */
export function severityCounts(
  findings: readonly Pick<GapFinding, "severity">[],
): string {
  const parts = (["high", "medium", "low"] as const)
    .map((s) => [s, findings.filter((f) => f.severity === s).length] as const)
    .filter(([, n]) => n > 0)
    .map(([s, n]) => `${n} ${s}`);
  return parts.length ? parts.join(" · ") : "no findings";
}

/** Findings and questions still waiting for Eric's decision. */
export function openItems(report: GapReport): number {
  return [...report.findings, ...report.questions].filter(
    (f) => f.disposition === "open",
  ).length;
}

export function exportUrl(analysisId: string): string {
  return `/api/gap-analyses/${encodeURIComponent(analysisId)}/export`;
}

/** Rejected findings as counts by guardrail, most first, e.g. "GX2 (source not returned …): 1". */
export function rejectedCounts(
  rejected: readonly GapFinding[],
): { guardrail: string; label: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const f of rejected)
    counts.set(
      f.rejection_guardrail,
      (counts.get(f.rejection_guardrail) ?? 0) + 1,
    );
  return [...counts.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([guardrail, count]) => ({
      guardrail,
      label: GUARDRAIL_LABELS[guardrail] ?? guardrail,
      count,
    }));
}

// --- The research brief (Analysis B) -------------------------------------------------------

export type DomainPolicy = "none" | "allowed" | "blocked";

export function domainPolicy(brief: Brief): DomainPolicy {
  if (brief.allowed_domains.length) return "allowed";
  if (brief.blocked_domains.length) return "blocked";
  return "none";
}

/** One entry per non-blank line. */
export function linesToList(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function without(text: string, hit: string): string {
  const pattern = new RegExp(
    escapeRegExp(hit).replace(/\s+/g, "[\\s,.;:!?'’\"-]+"),
    "gi",
  );
  return text
    .replace(pattern, " ")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([,.;:!?])/g, "$1")
    .trim();
}

/**
 * The brief with every occurrence of a scan hit taken out (Remove, PRD §5.4): the text of each
 * field, ignoring case and the punctuation between words; entries left empty are dropped.
 */
export function removeHit(brief: Brief, hit: string): Brief {
  const list = (items: readonly string[]) =>
    items.map((item) => without(item, hit)).filter(Boolean);
  return {
    ...brief,
    process_name: without(brief.process_name, hit),
    industry: without(brief.industry, hit),
    region: without(brief.region, hit),
    adjacent_industries: list(brief.adjacent_industries),
    steps: list(brief.steps),
    questions: list(brief.questions),
  };
}

/** Why Run research can't start yet, in plain words; null when it can. */
export function runBlocker(
  state: BriefState,
  researchEnabled: boolean,
  dirty: boolean,
): string | null {
  if (!researchEnabled)
    return "Web research is switched off. Turn it on in Settings first.";
  if (!dirty && state.scan.hits.length)
    return "Remove the highlighted items from the brief before running the research.";
  if (!state.confirmed)
    return "Tick “This brief contains no confidential information” before running the research.";
  return null;
}
