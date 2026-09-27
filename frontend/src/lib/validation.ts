// Field rules shared by forms (PRD §5.11). Messages match the backend's (actions/settings.py)
// so the owner sees the same sentence whether the check runs here or on the server.

import { changedFields, type StepForm } from "./stepForm";

export const OWNER_NAME_MESSAGE = "Please enter your name (up to 80 characters, no line breaks).";
export const API_KEY_MESSAGE =
  "That doesn't look like a Claude API key. Keys start with sk-ant-. Copy it again from the Claude Console.";

/** null when valid, otherwise the message to show under the field. */
export function validateOwnerName(value: string): string | null {
  const name = value.trim();
  if (!name || name.length > 80 || /[\r\n\t]/.test(name)) return OWNER_NAME_MESSAGE;
  return null;
}

export function validateApiKey(value: string): string | null {
  return /^sk-ant-[A-Za-z0-9_-]{13,293}$/.test(value.trim()) ? null : API_KEY_MESSAGE;
}

export const ENGAGEMENT_NAME_MESSAGE = "Please give the engagement a name (up to 120 characters).";

export function validateEngagementName(value: string): string | null {
  const name = value.trim();
  if (!name || name.length > 120 || /[\r\n]/.test(name)) return ENGAGEMENT_NAME_MESSAGE;
  return null;
}

// Scope-card rules (API_CONTRACT.md → Engagements): the same limits the server applies.
export const TEXT_LIMIT = 2000;
export const LIST_LIMIT = 50;
export const ITEM_LIMIT = 120;

export function validateScopeText(label: string, value: string): string | null {
  return value.trim().length > TEXT_LIMIT ? `${label}: at most ${TEXT_LIMIT} characters.` : null;
}

export function validateScopeList(label: string, values: readonly string[]): string | null {
  if (values.length > LIST_LIMIT) return `${label}: at most ${LIST_LIMIT} entries.`;
  if (values.some((v) => v.length > ITEM_LIMIT)) return `${label}: each entry must be one line of up to ${ITEM_LIMIT} characters.`;
  return null;
}

export const ROLE_NAME_MESSAGE = "Please give the role a name (up to 80 characters).";

export function validateRoleName(value: string): string | null {
  const name = value.trim();
  return !name || name.length > 80 || /[\r\n]/.test(name) ? ROLE_NAME_MESSAGE : null;
}

// Step rules (PRD §5.7.6): the same checks and sentences as the server (actions/review.py
// check_step), shared by the edit form, the table view's inline edits and Add step. Keys are the
// server's field names, so a message from either side lands under the same field.

const STEP_TEXT_LIMITS: readonly [keyof StepForm, string, number][] = [
  ["duration_text", "The time window", 200],
  ["kpi", "The KPI", 300],
  ["handoff_in", "Handoff in", 300],
  ["handoff_out", "Handoff out", 300],
  ["rule_or_threshold", "The rule or threshold", 500],
  ["escalation", "The escalation", 500],
  ["k_risk", "The knowledge risk", 500],
];
const SERVER_NAMES: Partial<Record<keyof StepForm, string>> = {
  handoff_in: "handoff.in",
  handoff_out: "handoff.out",
  rule_or_threshold: "decision.rule_or_threshold",
  escalation: "decision.escalation",
};

export type StepErrors = Record<string, string>;

function minutesOk(text: string): boolean {
  if (text.trim() === "") return true;
  const n = Number(text);
  return Number.isFinite(n) && n >= 0 && n <= 10000;
}

/**
 * The field rules for a step. With `original` (editing), RACI is checked only when RACI or kind
 * changed, as the server does: a drafted step with incomplete RACI can still get a new KPI.
 */
export function validateStep(form: StepForm, original?: StepForm): StepErrors {
  const errors: StepErrors = {};
  const label = form.label.trim();
  if (!label || label.length > 120 || /[\r\n]/.test(label)) {
    errors.label = "Please give the step a name of up to 120 characters.";
  }
  if (!form.lane_role_id) errors.lane_role_id = "Choose the lane (role) this step sits in.";
  for (const field of ["work_min", "wait_min"] as const) {
    if (!minutesOk(form[field])) errors[field] = "Minutes must be between 0 and 10,000.";
  }
  for (const [field, words, limit] of STEP_TEXT_LIMITS) {
    const value = form[field];
    if (typeof value === "string" && value.trim().length > limit) {
      errors[SERVER_NAMES[field] ?? field] = `${words} can be up to ${limit.toLocaleString("en-GB")} characters.`;
    }
  }
  const deciding = form.kind === "decision" || form.kind === "approval";
  if (deciding && form.mechanism !== "rule_based" && form.mechanism !== "judgment") {
    errors["decision.mechanism"] = "Say whether this decision or approval follows a rule or is a judgment call.";
  }
  if (form.constraints.some((c) => !c.text.trim())) errors.constraints = "A constraint needs some text.";
  const flag = form.ai_flag;
  if (flag) {
    if (!flag.input.trim()) errors["ai_flag.input"] = "An AI flag needs its input, output and handoff.";
    if (!flag.output.trim()) errors["ai_flag.output"] = "An AI flag needs its input, output and handoff.";
    if (!flag.handoff.trim()) errors["ai_flag.handoff"] = "An AI flag needs its input, output and handoff.";
    if (flag.basis === "rule_based_automate_candidate" && form.mechanism === "judgment") {
      errors["ai_flag.basis"] = "A judgment step is never an automation candidate. Choose support only.";
    }
  }
  const changed = original ? changedFields(original, form) : null;
  const checkRaci = !changed || "raci" in changed || "kind" in changed;
  if (!checkRaci) return errors;
  if (form.accountable.length === 0) errors.raci = "Choose who is Accountable for this step.";
  else if (form.kind === "activity" && !form.responsible) {
    errors.raci = "An activity needs exactly one Responsible role.";
  }
  return errors;
}
