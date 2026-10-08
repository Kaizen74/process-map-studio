import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import type { GapEvidence, GapFinding } from "../../src/lib/gap";
import {
  ALIGNMENT_STATUS_LABELS,
  basisText,
  spreadText,
  type ActivityMetrics,
  type Alignment,
  type AlignmentRow,
  type AlignmentSummary,
  type CaseMetrics,
  type DroppedRows,
  type EventLog,
  type MetricGroup,
  type MetricsResponse,
  type MonthVolume,
  type ResourceRow,
  type RoleMetrics,
  type Spread,
  type SystemTrace,
  type TraceActivity,
  type TransitionMetrics,
  type ValidationReport,
  type VariantMetrics,
} from "../../src/lib/systemRecords";

// What the backend really sends (written by backend/tests/unit/test_acceptance_p10b.py).
const SYSTEM = JSON.parse(
  readFileSync(join(__dirname, "..", "fixtures", "system_records.json"), "utf-8"),
) as {
  held_log: EventLog;
  imported_log: EventLog;
  metrics: {
    activity: MetricsResponse<ActivityMetrics>;
    transition: MetricsResponse<TransitionMetrics>;
    case: MetricsResponse<CaseMetrics>;
    variant: MetricsResponse<VariantMetrics>;
    role: MetricsResponse<RoleMetrics>;
  };
  alignment: Alignment;
  system_traces: SystemTrace[];
  system_findings: GapFinding[];
};

// Every field of each type, exactly (`satisfies` refuses a missing or an extra one).
const LOG = { id: 1, engagement_id: 1, name: 1, system: 1, timezone: 1, window_start: 1, window_end: 1, status: 1, column_map: 1, timestamp_format: 1, file_held: 1, resources: 1, role_map: 1, validation_report: 1, approved_by_role: 1, approved_at: 1, created_at: 1 } satisfies Record<keyof EventLog, 1>; // prettier-ignore
const REPORT = { rows_read: 1, rows_kept: 1, cases: 1, activities: 1, date_from: 1, date_to: 1, dropped: 1, dropped_share: 1, single_event_cases: 1, unknown_role_events: 1, outside_window: 1, timestamp_format: 1, missing_columns: 1, refused: 1, refusal: 1 } satisfies Record<keyof ValidationReport, 1>; // prettier-ignore
const DROPPED = { unparseable_time: 1, missing_case_or_activity: 1, duplicate: 1 } satisfies Record<keyof DroppedRows, 1>; // prettier-ignore
const RESOURCE = { value: 1, events: 1, suggested_role_id: 1 } satisfies Record<keyof ResourceRow, 1>; // prettier-ignore
const RESPONSE = { log_id: 1, scope: 1, minimum_cases: 1, groups: 1, too_few: 1 } satisfies Record<keyof MetricsResponse<unknown>, 1>; // prettier-ignore
const GROUP = { scope: 1, key: 1, label: 1, case_count: 1, metrics: 1 } satisfies Record<keyof MetricGroup<unknown>, 1>; // prettier-ignore
const SPREAD = { median_min: 1, p90_min: 1, n: 1 } satisfies Record<keyof Spread, 1>; // prettier-ignore
const MONTH = { month: 1, events: 1, cases: 1 } satisfies Record<keyof MonthVolume, 1>; // prettier-ignore
const ACTIVITY = { activity: 1, events: 1, cases: 1, cases_per_week: 1, cases_per_month: 1, months: 1, months_too_few: 1, work: 1, wait_before: 1, basis: 1, rework_cases: 1, rework_share: 1 } satisfies Record<keyof ActivityMetrics, 1>; // prettier-ignore
const TRANSITION = { from_activity: 1, to_activity: 1, count: 1, cases: 1, elapsed: 1, basis: 1, handoffs: 1 } satisfies Record<keyof TransitionMetrics, 1>; // prettier-ignore
const CASE = { cases: 1, events: 1, activities: 1, date_from: 1, date_to: 1, weeks: 1, cycle_time: 1, basis: 1, rework_cases: 1, rework_share: 1, handoffs: 1, handoffs_per_case: 1, variants: 1, exception_share: 1 } satisfies Record<keyof CaseMetrics, 1>; // prettier-ignore
const VARIANT = { rank: 1, activities: 1, cases: 1, share: 1, cumulative_share: 1 } satisfies Record<keyof VariantMetrics, 1>; // prettier-ignore
const ROLE = { role: 1, events: 1, cases: 1, activities: 1, work: 1 } satisfies Record<keyof RoleMetrics, 1>; // prettier-ignore
const ALIGNMENT = { log_id: 1, version_id: 1, rows: 1, summary: 1 } satisfies Record<keyof Alignment, 1>; // prettier-ignore
const ROW = { activity: 1, element_id: 1, element_label: 1, status: 1, confirmed: 1, proposed_by: 1, reason: 1, events: 1, cases: 1 } satisfies Record<keyof AlignmentRow, 1>; // prettier-ignore
const SUMMARY = { activities: 1, matched: 1, hidden_work: 1, no_system_record: 1, waiting: 1 } satisfies Record<keyof AlignmentSummary, 1>; // prettier-ignore
const TRACE = { element_id: 1, label: 1, stance: 1, log_id: 1, log_name: 1, system: 1, window_start: 1, window_end: 1, cases: 1, events: 1, cases_per_week: 1, rework_cases: 1, rework_share: 1, activities: 1, note: 1 } satisfies Record<keyof SystemTrace, 1>; // prettier-ignore
const TRACE_ACTIVITY = { activity: 1, cases: 1, events: 1, work: 1, wait_before: 1, basis: 1 } satisfies Record<keyof TraceActivity, 1>; // prettier-ignore
const EVIDENCE = { side: 1, source_id: 1, source_kind: 1, source_name: 1, stance: 1, segment_id: 1, anchor: 1, quote: 1, url: 1, tier: 1, page_age: 1, citation_id: 1 } satisfies Record<keyof GapEvidence, 1>; // prettier-ignore

const keys = (o: object) => Object.keys(o).sort();
const spreads = (...values: (Spread | null)[]) =>
  values.forEach((s) => s && expect(keys(s)).toEqual(keys(SPREAD)));

describe("the frontend's system-records types match what the backend sends (P10b)", () => {
  it("every field of a held log and of an imported log", () => {
    for (const log of [SYSTEM.held_log, SYSTEM.imported_log]) {
      expect(keys(log)).toEqual(keys(LOG));
      expect(keys(log.validation_report as ValidationReport)).toEqual(keys(REPORT));
      expect(keys((log.validation_report as ValidationReport).dropped)).toEqual(keys(DROPPED));
      log.resources.forEach((r) => expect(keys(r)).toEqual(keys(RESOURCE)));
    }
    expect(SYSTEM.held_log.file_held).toBe(true);
    expect(SYSTEM.held_log.resources.length).toBeGreaterThan(0); // so the loop above ran
    expect(SYSTEM.imported_log.resources).toEqual([]); // user IDs are gone after the import
  });

  it("every field of each metric scope", () => {
    const expected = { activity: ACTIVITY, transition: TRANSITION, case: CASE, variant: VARIANT, role: ROLE }; // prettier-ignore
    for (const [scope, body] of Object.entries(SYSTEM.metrics)) {
      expect(keys(body)).toEqual(keys(RESPONSE));
      expect(body.groups.length).toBeGreaterThan(0);
      for (const group of body.groups as MetricGroup<object>[]) {
        expect(keys(group)).toEqual(keys(GROUP));
        expect(group.case_count).toBeGreaterThanOrEqual(body.minimum_cases);
        expect(keys(group.metrics)).toEqual(keys(expected[scope as keyof typeof expected]));
      }
    }
    for (const g of SYSTEM.metrics.activity.groups) {
      spreads(g.metrics.work, g.metrics.wait_before);
      g.metrics.months.forEach((m) => expect(keys(m)).toEqual(keys(MONTH)));
    }
    SYSTEM.metrics.transition.groups.forEach((g) => spreads(g.metrics.elapsed));
    SYSTEM.metrics.case.groups.forEach((g) => spreads(g.metrics.cycle_time));
    SYSTEM.metrics.role.groups.forEach((g) => spreads(g.metrics.work));
  });

  it("every field of the alignment table, the system trace and a system finding", () => {
    expect(keys(SYSTEM.alignment)).toEqual(keys(ALIGNMENT));
    expect(keys(SYSTEM.alignment.summary)).toEqual(keys(SUMMARY));
    SYSTEM.alignment.rows.forEach((r) => expect(keys(r)).toEqual(keys(ROW)));
    const statuses = new Set(SYSTEM.alignment.rows.map((r) => r.status));
    expect([...statuses].sort()).toEqual(Object.keys(ALIGNMENT_STATUS_LABELS).sort()); // all four
    expect(SYSTEM.system_traces.length).toBeGreaterThan(0);
    for (const t of SYSTEM.system_traces) {
      expect(keys(t)).toEqual(keys(TRACE));
      t.activities.forEach((a) => {
        expect(keys(a)).toEqual(keys(TRACE_ACTIVITY));
        spreads(a.work, a.wait_before);
      });
    }
    expect(SYSTEM.system_findings.length).toBeGreaterThan(0);
    for (const f of SYSTEM.system_findings) {
      f.evidence.forEach((e) => expect(keys(e)).toEqual(keys(EVIDENCE)));
      expect(f.evidence.some((e) => e.side === "system" && e.quote === "")).toBe(true);
    }
  });
});

describe("plain words (P10b)", () => {
  it("says a spread, a time basis and an alignment status in words", () => {
    const report = SYSTEM.metrics.activity.groups.find((g) => g.key === "Loading report received");
    expect(spreadText(report?.metrics.work ?? null)).toBe("median 13.4 min · 90th percentile 26.6 min");
    expect(spreadText(null)).toBe("No times recorded");
    expect(basisText("wait")).toBe("Work and wait");
    expect(basisText("not_separable")).toBe("Working and waiting (not separable)");
    expect(ALIGNMENT_STATUS_LABELS.hidden_work).toBe("Hidden work (no step)");
  });
});
