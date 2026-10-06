// Exceptions, rework and workarounds (API_CONTRACT.md → GET /versions/{vid}/exceptions; X2).
// Types and the plain words the Exceptions lens and the register show. The backend decides
// which route each step is on; nothing here works that out.

export type StepRoute = "usual" | "exception" | "variation";

export interface ExceptionStep {
  element_id: string;
  label: string;
  route: StepRoute;
  workaround: boolean;
  condition: string;
}

export interface RouteExit {
  kind: "rejoins" | "loops_back" | "ends";
  element_id: string;
  label: string;
  edge_label: string;
}

export interface ExceptionRoute {
  id: string;
  kind: "exception" | "variation";
  from_element_id: string;
  from_label: string;
  condition: string;
  element_ids: string[];
  labels: string[];
  lanes: string[];
  exits: RouteExit[];
  handoffs: number;
  frequency: string;
  stated_reason: string;
}

export interface ReworkLoop {
  from_element_id: string;
  from_label: string;
  to_element_id: string;
  to_label: string;
  label: string;
}

export interface Workaround {
  element_id: string;
  label: string;
  lane: string;
  condition: string;
  stated_reason: string;
  frequency: string;
  basis: "stated_reason" | "story";
}

export interface ExceptionQuestion {
  question_id: string;
  wording: string;
  about: string;
}

export interface ExceptionSummary {
  steps: number;
  usual_steps: number;
  exception_steps: number;
  variation_steps: number;
  off_usual_share: number;
  routes: number;
  rework_loops: number;
  workarounds: number;
  extra_handoffs: number;
  frequency_stated: number;
}

export interface ExceptionReport {
  view: "done" | "documented";
  summary: ExceptionSummary;
  steps: ExceptionStep[];
  routes: ExceptionRoute[];
  loops: ReworkLoop[];
  workarounds: Workaround[];
  questions: ExceptionQuestion[];
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/**
 * The Exceptions lens line under a step: one short word, so it fits under the node (§5.5 visual
 * restraint). The condition is on the line into the step ("No", "Outside limits"); the register
 * gives each route in full.
 */
export function routeLine(step: ExceptionStep): string {
  if (step.workaround) return "Workaround";
  if (step.route === "exception") return "Exception";
  if (step.route === "variation") return "Variation";
  return "Usual route";
}

/** One line of facts: how much of the process is off the usual route. */
export function summaryText(s: ExceptionSummary): string {
  if (s.steps === 0) return "No steps in this view yet.";
  const off = s.exception_steps + s.variation_steps;
  if (off === 0 && s.rework_loops === 0 && s.workarounds === 0) {
    return `All ${plural(s.steps, "step", "steps")} are on the usual route; no exception routes, rework loops or workarounds.`;
  }
  const parts = [
    `${off} of ${plural(s.steps, "step", "steps")} (${Math.round(s.off_usual_share * 100)}%) are off the usual route: ${s.exception_steps} on exception routes, ${plural(s.variation_steps, "variation", "variations")}.`,
    `${plural(s.rework_loops, "rework loop", "rework loops")}; ${plural(s.workarounds, "workaround", "workarounds")}.`,
  ];
  if (s.extra_handoffs > 0) parts.push(`The exception routes add ${plural(s.extra_handoffs, "hand-over", "hand-overs")}.`);
  return parts.join(" ");
}

/** How a route ends, in words: "goes back to Draft load plan (Re-plan)". */
export function exitText(exit: RouteExit): string {
  const why = exit.edge_label ? ` (${exit.edge_label})` : "";
  if (exit.kind === "loops_back") return `goes back to ${exit.label}${why}`;
  if (exit.kind === "ends") return "ends the process";
  return `rejoins the usual route at ${exit.label}${why}`;
}

/** "How often: maybe once a month" or that it hasn't been said. */
export function frequencyText(frequency: string): string {
  return frequency ? `How often: ${frequency}` : "How often: not stated yet";
}

export const ROUTE_KIND_LABELS: Readonly<Record<ExceptionRoute["kind"], string>> = {
  exception: "Exception route",
  variation: "Variation",
};
