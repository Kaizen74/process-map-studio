import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  DISPOSITION_LABELS,
  EVIDENCE_LABELS,
  type Assumption,
  type DispositionRow,
  type RoleCostRow,
  type RoleCosts,
  type Scenario,
  type StepValue,
  type ValueFigure,
  type ValueReport,
  type ValueTotal,
} from "../../src/lib/value";

// What the backend really sends (written by backend/tests/unit/test_acceptance_p10b.py).
const SYSTEM = JSON.parse(readFileSync(join(__dirname, "..", "fixtures", "system_records.json"), "utf-8")) as {
  dispositions: DispositionRow[];
  role_costs: RoleCosts;
  value_assumptions: Assumption[];
  value: ValueReport;
};

// Every field of each type, exactly (`satisfies` refuses a missing or an extra one).
const ROW = { element_id: 1, label: 1, kind: 1, suggested: 1, reason: 1, disposition: 1, note: 1, risk_flag: 1, allowed: 1 } satisfies Record<keyof DispositionRow, 1>; // prettier-ignore
const COSTS = { currency: 1, rows: 1 } satisfies Record<keyof RoleCosts, 1>; // prettier-ignore
const COST = { role_id: 1, role_name: 1, hourly_cost: 1, note: 1 } satisfies Record<keyof RoleCostRow, 1>; // prettier-ignore
const ASSUMPTION = { disposition: 1, reduction_pct: 1, note: 1, default: 1 } satisfies Record<keyof Assumption, 1>; // prettier-ignore
const REPORT = { currency: 1, view: 1, potential: 1, steps: 1, phases: 1, totals: 1, scenarios: 1 } satisfies Record<keyof ValueReport, 1>; // prettier-ignore
const STEP = { element_id: 1, label: 1, phase_id: 1, phase_name: 1, role_name: 1, time: 1, volume: 1, hours_per_month: 1, cost_per_month: 1, evidence: 1, missing: 1, disposition: 1, chosen: 1, reduction_pct: 1, hours_released: 1, cost_released: 1 } satisfies Record<keyof StepValue, 1>; // prettier-ignore
const FIGURE = { value: 1, label: 1, source: 1 } satisfies Record<keyof ValueFigure, 1>; // prettier-ignore
const TOTAL = { phase_id: 1, name: 1, hours_per_month: 1, cost_per_month: 1, evidence: 1, steps_counted: 1, steps_missing: 1, steps_without_cost: 1 } satisfies Record<keyof ValueTotal, 1>; // prettier-ignore
const SCENARIO = { disposition: 1, reduction_pct: 1, steps: 1, hours_per_month: 1, hours_released: 1, cost_released: 1 } satisfies Record<keyof Scenario, 1>; // prettier-ignore

const keys = (o: object) => Object.keys(o).sort();

describe("the frontend's value and disposition types match what the backend sends (R9)", () => {
  it("every field of the dispositions, role costs and assumptions", () => {
    expect(SYSTEM.dispositions.length).toBeGreaterThan(0);
    SYSTEM.dispositions.forEach((r) => {
      expect(keys(r)).toEqual(keys(ROW));
      expect(DISPOSITION_LABELS[r.suggested]).toBeTruthy();
    });
    expect(SYSTEM.dispositions.some((r) => r.disposition === "automate_rules")).toBe(true);
    expect(keys(SYSTEM.role_costs)).toEqual(keys(COSTS));
    SYSTEM.role_costs.rows.forEach((r) => expect(keys(r)).toEqual(keys(COST)));
    expect(SYSTEM.value_assumptions.map((a) => a.disposition)).toEqual(Object.keys(DISPOSITION_LABELS));
    SYSTEM.value_assumptions.forEach((a) => expect(keys(a)).toEqual(keys(ASSUMPTION)));
  });

  it("every field of the value report, with every figure labelled", () => {
    const v = SYSTEM.value;
    expect(keys(v)).toEqual(keys(REPORT));
    expect(v.potential).toBe("Potential, not committed");
    for (const s of v.steps) {
      expect(keys(s)).toEqual(keys(STEP));
      [s.time, s.volume].forEach((f) => f && expect(keys(f)).toEqual(keys(FIGURE)));
      if (s.hours_per_month !== null) expect(EVIDENCE_LABELS[s.evidence ?? "mixed"]).toBeTruthy();
      else expect(s.evidence).toBeNull();
    }
    expect(v.steps.some((s) => s.cost_per_month !== null && s.volume?.label === "measured")).toBe(true);
    expect(v.steps.some((s) => s.volume?.label === "assumed")).toBe(true);
    [...v.phases, v.totals].forEach((t) => expect(keys(t)).toEqual(keys(TOTAL)));
    v.scenarios.forEach((s) => expect(keys(s)).toEqual(keys(SCENARIO)));
  });
});
