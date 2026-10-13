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

export type RegisterKey =
  | "k_risk"
  | "ai_flags"
  | "constraints"
  | "external"
  | "questions"
  | "rejected"
  | "causes"
  | "themes"
  | "boundaries"
  | "exceptions"
  | "stories"
  | "glossary"
  | "preserve"
  | "value";

/** GET /versions/{vid}/lane-boundaries (C8): teams' activities overlapping or falling between them. */
export type BoundaryKind = "shared_delivery" | "gap" | "boundary";

export interface LaneBoundary {
  element_id: string;
  label: string;
  kind: BoundaryKind | string;
  responsible: string;
  consulted: string[];
  note: string;
  question_ids: string[];
}

export const BOUNDARY_KIND_LABELS: Readonly<Record<BoundaryKind, string>> = {
  shared_delivery: "Shared delivery",
  gap: "Falls between teams",
  boundary: "Boundary discussed",
};

export function boundaryKindLabel(kind: string): string {
  return BOUNDARY_KIND_LABELS[kind as BoundaryKind] ?? kind;
}

/** GET /engagements/{id}/themes (C7b): a pattern across two or more stories. */
export type ThemeStatus = "proposed" | "accepted" | "dismissed";

export interface ThemeFragment {
  claim_id: string;
  text: string;
  quote: string;
  fragment_type: string;
  source_id: string;
  anchor: string;
}

export interface Theme {
  id: string;
  version_id: string | null;
  theme: string;
  basis: string;
  status: ThemeStatus | string;
  note: string;
  fragments: ThemeFragment[];
  created_at: string;
}

export const REGISTERS: readonly { value: RegisterKey; label: string }[] = [
  { value: "k_risk", label: "K-RISK" },
  { value: "ai_flags", label: "AI flags" },
  { value: "constraints", label: "Constraints by cause" },
  { value: "external", label: "External practice (R)" },
  { value: "questions", label: "Validation questions" },
  { value: "rejected", label: "Rejected claims" },
  { value: "stories", label: "Stories" },
  { value: "glossary", label: "Glossary" },
  { value: "causes", label: "Cause library" },
  { value: "themes", label: "Emerging themes" },
  { value: "preserve", label: "Preserve / Improve" },
  { value: "boundaries", label: "Lane boundaries" },
  { value: "exceptions", label: "Exceptions and workarounds" },
];

/** Disposition and value (R10c): listed only while the value module is on (decision A). */
export const VALUE_REGISTER: { value: RegisterKey; label: string } = { value: "value", label: "Disposition and value" };

/** The registers to offer: the value register joins the list while its module is on. */
export function registerOptions(valueOn: boolean): readonly { value: RegisterKey; label: string }[] {
  return valueOn ? [...REGISTERS, VALUE_REGISTER] : REGISTERS;
}

export function registerKey(value: string | null, options = REGISTERS): RegisterKey {
  return options.find((r) => r.value === value)?.value ?? "k_risk";
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

/** B.36 capability dimensions, in the PRD's order, in plain words (Preserve / Improve, P9u). */
export const CAPABILITY_DIMENSIONS: readonly { value: string; label: string }[] = [
  { value: "skillset", label: "Skillset" },
  { value: "ways_of_working", label: "Ways of working" },
  { value: "systems", label: "Systems" },
  { value: "process", label: "Process" },
  { value: "structure", label: "Structure" },
];

export function dimensionLabel(value: string): string {
  return CAPABILITY_DIMENSIONS.find((d) => d.value === value)?.label ?? value;
}

/** Notes grouped by dimension in the PRD's order; an unknown dimension goes last, as given. */
export function byDimension<T extends { dimension: string }>(notes: readonly T[]): { dimension: string; label: string; notes: T[] }[] {
  const known = CAPABILITY_DIMENSIONS.map((d) => d.value);
  const order = [...known, ...notes.map((n) => n.dimension).filter((d) => !known.includes(d))];
  return [...new Set(order)]
    .map((dimension) => ({ dimension, label: dimensionLabel(dimension), notes: notes.filter((n) => n.dimension === dimension) }))
    .filter((group) => group.notes.length > 0);
}
