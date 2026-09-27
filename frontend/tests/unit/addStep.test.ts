import { describe, expect, it } from "vitest";
import { NEEDS_PASSAGE, NEEDS_REFERENCE, newStepBody, newStepForm, placesAfter, validateNewStep } from "../../src/lib/addStep";
import { SAMPLE, elementByLabel } from "../sampleMap";

const PASSAGE = { id: "s1", anchor: "06:40", source_name: "interview.txt", text: "We check the fuel." };

describe("add missing step (PRD §5.7.6)", () => {
  it("starts after the chosen step, in its lane, observed, with a passage if one was given", () => {
    const plan = elementByLabel("Draft load plan");
    const form = newStepForm(SAMPLE.graph, plan.id, PASSAGE);
    expect(form).toMatchObject({ after_element_id: plan.id, lane_role_id: plan.lane_role_id, provenance: "O" });
    expect(form.passages).toEqual([PASSAGE]);
  });

  it("can go after the start or any step, never after the end or a rejected step", () => {
    const graph = structuredClone(SAMPLE.graph);
    graph.elements = graph.elements.map((e) => (e.label === "Issue load sheet" ? { ...e, review_status: "rejected" } : e));
    const labels = placesAfter(graph).map((p) => p.label);
    expect(labels[0]).toBe("Flight scheduled (start)");
    expect(labels).not.toContain("Issue load sheet");
    expect(labels).not.toContain("Final load sheet issued");
  });

  it("an observed step needs a passage; a recommended one a reference", () => {
    const form = { ...newStepForm(SAMPLE.graph, elementByLabel("Draft load plan").id), label: "Check fuel" };
    expect(validateNewStep(form)).toEqual({ segment_ids: NEEDS_PASSAGE });
    expect(validateNewStep({ ...form, provenance: "R", r_reference: " " })).toEqual({ r_reference: NEEDS_REFERENCE });
    expect(validateNewStep({ ...form, provenance: "R", r_reference: "x".repeat(501) })).toEqual({ r_reference: NEEDS_REFERENCE });
    expect(validateNewStep({ ...form, passages: [PASSAGE] })).toEqual({});
  });

  it("sends only what the provenance needs, and a mechanism only for decisions and approvals", () => {
    const form = {
      ...newStepForm(SAMPLE.graph, "a", PASSAGE),
      label: " Check fuel ",
      r_reference: "left over",
      mechanism: "rule_based",
    };
    expect(newStepBody(form)).toMatchObject({ label: "Check fuel", segment_ids: ["s1"], r_reference: "", mechanism: "judgment" });
    const recommended = newStepBody({ ...form, kind: "approval", provenance: "R" });
    expect(recommended).toMatchObject({ segment_ids: [], r_reference: "left over", mechanism: "rule_based" });
  });
});
