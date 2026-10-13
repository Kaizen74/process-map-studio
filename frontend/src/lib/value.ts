// Step disposition and the value calculator (API_CONTRACT.md → Step disposition, Value
// calculator; PRD §3.14-3.15; R9): the shapes the backend sends and the words the screens use.
// The backend works out every figure and suggestion; nothing here computes one.

export type Disposition = "delete" | "automate_rules" | "ai_assisted" | "human_approves" | "keep_human";
export type RiskFlag = "none" | "financial" | "safety" | "regulatory";
export type Evidence = "measured" | "estimated" | "mixed" | "assumed";

export const DISPOSITION_LABELS: Readonly<Record<Disposition, string>> = {
  delete: "Delete",
  automate_rules: "Automate (rules)",
  ai_assisted: "AI-assisted",
  human_approves: "Human approves",
  keep_human: "Keep human",
};

export const EVIDENCE_LABELS: Readonly<Record<Evidence, string>> = {
  measured: "Measured",
  estimated: "Estimated",
  mixed: "Mixed",
  assumed: "Assumed",
};

export const DISPOSITIONS = Object.keys(DISPOSITION_LABELS) as Disposition[];

export const RISK_FLAG_LABELS: Readonly<Record<RiskFlag, string>> = {
  none: "No particular risk",
  financial: "Financial risk",
  safety: "Safety risk",
  regulatory: "Regulatory risk",
};

/** A disposition Eric can't choose for a step, with the backend's reason (R10b). */
export interface RefusedDisposition {
  disposition: Disposition;
  reason: string;
}

/** A step's suggested disposition with its reason, and Eric's choice. */
export interface DispositionRow {
  element_id: string;
  label: string;
  kind: string;
  suggested: Disposition;
  reason: string;
  disposition: Disposition | null;
  note: string;
  risk_flag: RiskFlag;
  allowed: Disposition[];
  not_allowed: RefusedDisposition[];
}

/** PUT /elements/{eid}/disposition: `null` clears Eric's choice; a risk flag left out keeps its value. */
export interface DispositionChoice {
  disposition: Disposition | null;
  note: string;
  risk_flag?: RiskFlag;
}

/** PUT /elements/{eid}/value-override: Eric's own figures, with where they come from. */
export interface ValueOverride {
  time_min: number | null;
  volume_month: number | null;
  note: string;
}

export interface RoleCostRow {
  role_id: string;
  role_name: string;
  hourly_cost: number | null;
  note: string;
}

export interface RoleCosts {
  currency: string;
  rows: RoleCostRow[];
}

export interface Assumption {
  disposition: Disposition;
  reduction_pct: number;
  note: string;
  default: boolean;
}

export interface ValueFigure {
  value: number;
  label: Exclude<Evidence, "mixed">;
  source: string;
}

export interface StepValue {
  element_id: string;
  label: string;
  phase_id: string | null;
  phase_name: string;
  role_name: string;
  time: ValueFigure | null;
  volume: ValueFigure | null;
  hours_per_month: number | null;
  cost_per_month: number | null;
  evidence: Evidence | null;
  missing: string[];
  disposition: Disposition;
  chosen: boolean;
  reduction_pct: number;
  hours_released: number | null;
  cost_released: number | null;
}

export interface ValueTotal {
  phase_id: string | null;
  name: string;
  hours_per_month: number;
  cost_per_month: number;
  evidence: Evidence | null;
  steps_counted: number;
  steps_missing: number;
  steps_without_cost: number;
}

export interface Scenario {
  disposition: Disposition;
  reduction_pct: number;
  steps: number;
  hours_per_month: number;
  hours_released: number;
  cost_released: number;
}

/** Scenarios are always "Potential, not committed" (§3.14 presentation rules). */
export interface ValueReport {
  currency: string;
  view: "done" | "documented";
  potential: string;
  steps: StepValue[];
  phases: ValueTotal[];
  totals: ValueTotal;
  scenarios: Scenario[];
}

/** Money with its currency code, never per person: "SGD 1,723.20". */
export function money(value: number, currency: string): string {
  return `${currency} ${value.toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Hours a month: "35.9 h a month". */
export function hoursText(value: number): string {
  return `${value.toLocaleString("en-GB", { maximumFractionDigits: 1 })} h a month`;
}

/** A figure with its unit and evidence label, as the panel words it. */
export function figureText(figure: ValueFigure, unit: "min a case" | "cases a month"): string {
  const value = figure.value.toLocaleString("en-GB", { maximumFractionDigits: 1 });
  return `${value} ${unit} · ${EVIDENCE_LABELS[figure.label].toLowerCase()}`;
}

