// Registers and the cause library (API_CONTRACT.md → GET /versions/{vid}/registers, Cause
// library; PRD §5.4 Registers). In lib so components can type their props without src/api.
import type { Question, RejectedClaims } from "./reviewTypes";

export interface KRiskItem {
  element_id: string;
  label: string;
  lane: string;
  k_risk: string;
}

export interface AiFlagItem {
  element_id: string;
  label: string;
  lane: string;
  mechanism: string;
  component: string;
  input: string;
  output: string;
  handoff: string;
  basis: string;
}

export interface ConstraintItem {
  element_id: string;
  label: string;
  text: string;
  is_key: boolean;
  provenance: string;
}

export interface ConstraintGroup {
  cause_type: string | null;
  constraints: ConstraintItem[];
}

export interface ExternalPracticeItem {
  element_id: string;
  label: string;
  r_reference: string;
}

export interface Registers {
  k_risk: KRiskItem[];
  ai_flags: AiFlagItem[];
  constraints_by_cause: ConstraintGroup[];
  external_practice: ExternalPracticeItem[];
  questions: Question[];
  rejected_claims: RejectedClaims;
}

export type ValidationResult = "pending" | "confirmed" | "refuted";

export interface CauseEntry {
  id: string;
  element_stable_key: string;
  element_id: string | null;
  element_label: string;
  divergence_type: string;
  pattern: string;
  inferred_cause: string;
  cause_type: string | null;
  provenance: string;
  validation_result: ValidationResult | string;
  created_at: string;
}

export type RegisterKey = "k_risk" | "ai_flags" | "constraints" | "external" | "questions" | "rejected" | "causes";

export const REGISTERS: readonly { value: RegisterKey; label: string }[] = [
  { value: "k_risk", label: "K-RISK" },
  { value: "ai_flags", label: "AI flags" },
  { value: "constraints", label: "Constraints by cause" },
  { value: "external", label: "External practice (R)" },
  { value: "questions", label: "Validation questions" },
  { value: "rejected", label: "Rejected claims" },
  { value: "causes", label: "Cause library" },
];

export function registerKey(value: string | null): RegisterKey {
  return REGISTERS.find((r) => r.value === value)?.value ?? "k_risk";
}

/** B.9 cause types, in plain words. */
const CAUSE_TYPES: Readonly<Record<string, string>> = {
  decision_rights: "Decision rights",
  system_fragmentation: "System fragmentation",
  single_point_knowledge: "Single-point knowledge",
  capacity_mismatch: "Capacity mismatch",
  policy_control: "Policy or control",
  capability_gap: "Capability gap",
};

export function causeTypeLabel(type: string | null): string {
  return type === null ? "No cause type recorded" : (CAUSE_TYPES[type] ?? type);
}

/** B.11 AI components and B.12 bases, in plain words. */
const COMPONENTS: Readonly<Record<string, string>> = {
  perception: "Perception",
  knowledge_base: "Knowledge base",
  reasoning: "Reasoning",
  learning: "Learning",
  communication: "Communication",
  action: "Action",
};

export function componentLabel(component: string): string {
  return COMPONENTS[component] ?? component;
}

export function basisLabel(basis: string, mechanism: string): string {
  // A judgment step is never an automation candidate (constraint 7), whatever the flag says.
  if (mechanism === "judgment" || basis === "judgment_support_only") return "Judgment: support only";
  return "Rule-based: an automation candidate";
}

export const VALIDATION_LABELS: Readonly<Record<string, string>> = {
  pending: "Pending",
  confirmed: "Confirmed",
  refuted: "Refuted",
};
