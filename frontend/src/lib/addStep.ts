// Add missing step (PRD §5.7.6; API_CONTRACT.md → Review: POST /versions/{vid}/elements). Eric's
// own step, never an AI claim: Observed (O) with the passages he picked, or Recommended (R) with
// his typed reference. Pure; the same rules and sentences as the server (actions/map_edits.py).

import type { Graph } from "./mapTypes";

export interface PickedPassage {
  id: string;
  anchor: string;
  source_name: string;
  text: string;
}

export type AddProvenance = "O" | "R";

export interface AddStepForm {
  label: string;
  kind: string;
  lane_role_id: string;
  after_element_id: string;
  provenance: AddProvenance;
  passages: PickedPassage[];
  r_reference: string;
  mechanism: string;
}

export const PROVENANCES: readonly { value: AddProvenance; label: string }[] = [
  { value: "O", label: "Observed in a source" },
  { value: "R", label: "Recommended practice" },
];

export const DECIDING_MECHANISMS = [
  { value: "judgment", label: "Judgment" },
  { value: "rule_based", label: "Rule-based" },
] as const;

export const NEEDS_PASSAGE = "Pick the passage this step comes from.";
export const NEEDS_REFERENCE = "Type the reference this recommended step comes from.";

/** A new form: after `afterId`, in that step's lane, observed (with a passage if one was given). */
export function newStepForm(graph: Graph, afterId: string, passage?: PickedPassage): AddStepForm {
  const after = graph.elements.find((e) => e.id === afterId);
  return {
    label: "",
    kind: "activity",
    lane_role_id: after?.lane_role_id ?? "",
    after_element_id: afterId,
    provenance: "O",
    passages: passage ? [passage] : [],
    r_reference: "",
    mechanism: "judgment",
  };
}

/** Where a new step can go: after any step or the start, never after the end or a rejected step. */
export function placesAfter(graph: Graph): { value: string; label: string }[] {
  return graph.elements
    .filter((e) => e.kind !== "end" && e.review_status !== "rejected")
    .map((e) => ({ value: e.id, label: e.kind === "start" ? `${e.label} (start)` : e.label }));
}

export function validateNewStep(form: AddStepForm): Record<string, string> {
  const errors: Record<string, string> = {};
  const label = form.label.trim();
  if (!label || label.length > 120 || /[\r\n]/.test(label)) {
    errors.label = "Please give the step a name of up to 120 characters.";
  }
  if (!form.lane_role_id) errors.lane_role_id = "Choose the lane (role) this step sits in.";
  if (!form.after_element_id) errors.after_element_id = "Choose the step the new one comes after.";
  if (form.provenance === "O" && form.passages.length === 0) errors.segment_ids = NEEDS_PASSAGE;
  const reference = form.r_reference.trim();
  if (form.provenance === "R" && (!reference || reference.length > 500)) errors.r_reference = NEEDS_REFERENCE;
  return errors;
}

/** The POST body: only what the chosen provenance needs. */
export function newStepBody(form: AddStepForm) {
  const deciding = form.kind === "decision" || form.kind === "approval";
  return {
    kind: form.kind,
    label: form.label.trim(),
    lane_role_id: form.lane_role_id,
    after_element_id: form.after_element_id,
    provenance: form.provenance,
    segment_ids: form.provenance === "O" ? form.passages.map((p) => p.id) : [],
    r_reference: form.provenance === "R" ? form.r_reference.trim() : "",
    mechanism: deciding ? form.mechanism : "judgment",
  };
}

export type NewStepBody = ReturnType<typeof newStepBody>;
