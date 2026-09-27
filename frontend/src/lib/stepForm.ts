// The edit form's data (PRD §5.7.6): an element turned into form fields and back into the
// PATCH /elements/{eid} body. Pure; the field rules are in validation.ts.

import type { GraphElement } from "./mapTypes";

export interface ConstraintRow {
  text: string;
  cause_type: string;
  is_key: boolean;
  provenance: string;
}

export interface AiFlagFields {
  component: string;
  input: string;
  output: string;
  handoff: string;
  basis: string;
}

export interface StepForm {
  label: string;
  kind: string;
  lane_role_id: string;
  responsible: string; // "" = none
  accountable: string[];
  consulted: string[];
  informed: string[];
  work_min: string;
  wait_min: string;
  duration_text: string;
  complexity: string;
  kpi: string;
  mechanism: string;
  decider_role_id: string;
  rule_or_threshold: string;
  escalation: string;
  handoff_in: string;
  handoff_out: string;
  constraints: ConstraintRow[];
  k_risk: string;
  ai_flag: AiFlagFields | null;
}

export const KINDS = [
  { value: "activity", label: "Activity" },
  { value: "decision", label: "Decision" },
  { value: "approval", label: "Approval" },
] as const;

export const MECHANISMS = [
  { value: "rule_based", label: "Rule-based" },
  { value: "judgment", label: "Judgment" },
  { value: "none", label: "Not stated" },
] as const;

export const CAUSE_TYPES = [
  { value: "", label: "Not stated" },
  { value: "decision_rights", label: "Decision rights" },
  { value: "system_fragmentation", label: "System fragmentation" },
  { value: "single_point_knowledge", label: "Single point knowledge" },
  { value: "capacity_mismatch", label: "Capacity mismatch" },
  { value: "policy_control", label: "Policy control" },
  { value: "capability_gap", label: "Capability gap" },
] as const;

export const AI_COMPONENTS = [
  { value: "perception", label: "Perception" },
  { value: "knowledge_base", label: "Knowledge base" },
  { value: "reasoning", label: "Reasoning" },
  { value: "learning", label: "Learning" },
  { value: "communication", label: "Communication" },
  { value: "action", label: "Action" },
] as const;

export const AI_BASES = [
  { value: "rule_based_automate_candidate", label: "Rule-based: an automation candidate" },
  { value: "judgment_support_only", label: "Judgment: support the person, never automate" },
] as const;

const minutes = (value: number | null) => (value === null ? "" : String(value));

/** What the form reads: a step from the graph (table view) or the panel's details (edit form). */
export type StepSource = Pick<
  GraphElement,
  "label" | "kind" | "lane_role_id" | "time" | "complexity" | "kpi" | "decision" | "handoff" | "constraints" | "k_risk" | "ai_flag"
> & { raci: readonly { role_id: string; letter: string }[] };

export function formFrom(e: StepSource): StepForm {
  const letters = (letter: string) => e.raci.filter((r) => r.letter === letter).map((r) => r.role_id);
  return {
    label: e.label,
    kind: e.kind,
    lane_role_id: e.lane_role_id ?? "",
    responsible: letters("R")[0] ?? "",
    accountable: letters("A"),
    consulted: letters("C"),
    informed: letters("I"),
    work_min: minutes(e.time.work_min),
    wait_min: minutes(e.time.wait_min),
    duration_text: e.time.text,
    complexity: e.complexity ?? "",
    kpi: e.kpi,
    mechanism: e.decision.mechanism,
    decider_role_id: e.decision.decider_role_id ?? "",
    rule_or_threshold: e.decision.rule_or_threshold,
    escalation: e.decision.escalation,
    handoff_in: e.handoff.in,
    handoff_out: e.handoff.out,
    constraints: e.constraints.map((c) => ({
      text: c.text,
      cause_type: c.cause_type ?? "",
      is_key: c.is_key,
      provenance: c.provenance,
    })),
    k_risk: e.k_risk,
    ai_flag: e.ai_flag ? { ...e.ai_flag } : null,
  };
}

const toMinutes = (text: string) => (text.trim() === "" ? null : Number(text));

/** The PATCH body for every field of the form. */
export function patchFrom(form: StepForm) {
  const several = form.accountable.length > 1; // several Accountable roles are always contested
  return {
    label: form.label.trim(),
    kind: form.kind,
    lane_role_id: form.lane_role_id,
    work_min: toMinutes(form.work_min),
    wait_min: toMinutes(form.wait_min),
    duration_text: form.duration_text.trim(),
    complexity: form.complexity || null,
    kpi: form.kpi.trim(),
    decision: {
      mechanism: form.mechanism,
      decider_role_id: form.decider_role_id || null,
      rule_or_threshold: form.rule_or_threshold.trim(),
      escalation: form.escalation.trim(),
    },
    handoff: { in: form.handoff_in.trim(), out: form.handoff_out.trim() },
    constraints: form.constraints.map((c) => ({
      text: c.text.trim(),
      cause_type: c.cause_type || null,
      is_key: c.is_key,
      provenance: c.provenance,
    })),
    k_risk: form.k_risk.trim(),
    ai_flag: form.ai_flag
      ? {
          component: form.ai_flag.component,
          input: form.ai_flag.input.trim(),
          output: form.ai_flag.output.trim(),
          handoff: form.ai_flag.handoff.trim(),
          basis: form.ai_flag.basis,
        }
      : null,
    raci: [
      ...(form.responsible ? [{ role_id: form.responsible, letter: "R", contested: false }] : []),
      ...form.accountable.map((role_id) => ({ role_id, letter: "A", contested: several })),
      ...form.consulted.map((role_id) => ({ role_id, letter: "C", contested: false })),
      ...form.informed.map((role_id) => ({ role_id, letter: "I", contested: false })),
    ],
  };
}

export type StepPatch = ReturnType<typeof patchFrom>;

/**
 * Only the fields Eric changed, so a Save with nothing changed sends nothing and a field the form
 * can't show exactly (such as a contested flag on RACI that wasn't touched) is never rewritten.
 */
export function changedFields(original: StepForm, form: StepForm): Partial<StepPatch> {
  const before = patchFrom(original);
  const after = patchFrom(form);
  const changed: Partial<StepPatch> = {};
  for (const key of Object.keys(after) as (keyof StepPatch)[]) {
    if (JSON.stringify(before[key]) !== JSON.stringify(after[key])) {
      Object.assign(changed, { [key]: after[key] });
    }
  }
  return changed;
}
