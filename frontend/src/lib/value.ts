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
