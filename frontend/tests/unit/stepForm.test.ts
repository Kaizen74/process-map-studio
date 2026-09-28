import { describe, expect, it } from "vitest";
import { isTyping } from "../../src/lib/keys";
import { changedFields, formFrom, patchFrom } from "../../src/lib/stepForm";
import { validateStep } from "../../src/lib/validation";
import { SAMPLE, elementByLabel } from "../sampleMap";

const detail = (label: string) => {
  const found = SAMPLE.elements[elementByLabel(label).id];
  if (!found) throw new Error(label);
  return found;
};

describe("the edit form's data (PRD §5.7.6)", () => {
  it("turns a step into form fields and back without changing anything", () => {
    const form = formFrom(detail("Draft load plan"));
    expect(form.label).toBe("Draft load plan");
    expect(form.responsible).toBe("id-2");
    expect(form.accountable).toEqual(["id-2"]);
    expect(form.work_min).toBe("20");
    expect(changedFields(form, { ...form })).toEqual({});
  });

  it("sends only what changed, trimmed, with minutes as numbers", () => {
    const form = formFrom(detail("Draft load plan"));
    const patch = changedFields(form, { ...form, label: " Build the load plan ", wait_min: "5" });
    expect(patch).toEqual({ label: "Build the load plan", wait_min: 5 });
  });

  it("marks several Accountable roles as contested and sends RACI whole when it changes", () => {
    const form = formFrom(detail("Draft load plan"));
    const patch = changedFields(form, { ...form, accountable: ["id-2", "id-3"], informed: ["id-4"] });
    expect(patch.raci).toEqual([
      { role_id: "id-2", letter: "R", contested: false },
      { role_id: "id-2", letter: "A", contested: true },
      { role_id: "id-3", letter: "A", contested: true },
      { role_id: "id-4", letter: "I", contested: false },
    ]);
  });

  it("an empty minutes field means not stated, and removing the AI flag sends null", () => {
    const form = formFrom(detail("Special loads OK?"));
    expect(form.ai_flag).not.toBeNull();
    expect(patchFrom({ ...form, work_min: " " }).work_min).toBeNull();
    expect(changedFields(form, { ...form, ai_flag: null })).toEqual({ ai_flag: null });
  });
});

describe("validateStep (the same rules and sentences as the server)", () => {
  const plan = formFrom(detail("Draft load plan"));

  it("passes a drafted step as it is", () => {
    expect(validateStep(plan, plan)).toEqual({});
  });

  it("requires a name, a lane and sensible minutes", () => {
    expect(validateStep({ ...plan, label: "  ", lane_role_id: "", work_min: "-1", wait_min: "abc" })).toEqual({
      label: "Please give the step a name of up to 120 characters.",
      lane_role_id: "Choose the lane (role) this step sits in.",
      work_min: "Minutes must be between 0 and 10,000.",
      wait_min: "Minutes must be between 0 and 10,000.",
    });
  });

  it("names long texts with the server's field names", () => {
    const errors = validateStep({ ...plan, kpi: "k".repeat(301), handoff_in: "h".repeat(301) });
    expect(errors).toEqual({
      kpi: "The KPI can be up to 300 characters.",
      "handoff.in": "Handoff in can be up to 300 characters.",
    });
  });

  it("requires Accountable, and Responsible for an activity", () => {
    expect(validateStep({ ...plan, accountable: [] }).raci).toBe("Choose who is Accountable for this step.");
    expect(validateStep({ ...plan, responsible: "" }).raci).toBe("An activity needs exactly one Responsible role.");
    const approval = formFrom(detail("Approve deviation"));
    expect(validateStep(approval)).toEqual({}); // an approval needs no Responsible role
  });

  it("checks RACI on an edit only when RACI or kind changed, as the server does", () => {
    const special = formFrom(detail("Special loads OK?"));
    const noR = { ...special, kind: "activity" };
    expect(validateStep(noR, special).raci).toBe("An activity needs exactly one Responsible role.");
    const plain = { ...plan, responsible: "" };
    const edited = { ...plain, kpi: "Plan issued by T-90" };
    expect(validateStep(edited, plain)).toEqual({}); // RACI untouched: not checked
  });

  it("a decision needs its mechanism; a judgment step is never an automation candidate", () => {
    const deviation = formFrom(detail("Deviation in limits?"));
    expect(validateStep({ ...deviation, mechanism: "none" })["decision.mechanism"]).toBe(
      "Say whether this decision or approval follows a rule or is a judgment call.",
    );
    const flag = { component: "reasoning", input: "Weights", output: "", handoff: "Captain", basis: "rule_based_automate_candidate" };
    expect(validateStep({ ...deviation, ai_flag: flag })).toEqual({
      "ai_flag.output": "An AI flag needs its input, output and handoff.",
      "ai_flag.basis": "A judgment step is never an automation candidate. Choose support only.",
    });
  });

  it("a constraint needs some text", () => {
    const row = { text: " ", cause_type: "", is_key: false, provenance: "O" };
    expect(validateStep({ ...plan, constraints: [row] }).constraints).toBe("A constraint needs some text.");
  });
});

describe("isTyping (shortcuts leave fields alone, PRD §5.8)", () => {
  it.each([
    ["input", "text", true],
    ["input", "checkbox", false],
    ["textarea", "", true],
    ["select", "", true],
    ["button", "", false],
  ])("%s %s → %s", (tag, type, expected) => {
    const element = document.createElement(tag);
    if (type) element.setAttribute("type", type);
    expect(isTyping(element)).toBe(expected);
  });
  it("a plain input with no type counts as typing; no target does not", () => {
    expect(isTyping(document.createElement("input"))).toBe(true);
    expect(isTyping(null)).toBe(false);
  });
});
