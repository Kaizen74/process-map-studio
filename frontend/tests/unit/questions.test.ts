import { describe, expect, it } from "vitest";
import { WHOLE_PROCESS, byPhase, questionsFileName, questionsMarkdown } from "../../src/lib/questions";
import type { Question } from "../../src/lib/reviewTypes";

const q = (id: string, phase: string, status = "open", reason = "gap", label = ""): Question => ({
  id,
  element_id: label ? `e-${id}` : null,
  element_label: label,
  phase_id: phase ? `p-${phase}` : null,
  phase_name: phase,
  question: `Question ${id}?`,
  reason,
  status,
});

describe("validation questions (PRD §5.7.10)", () => {
  it("groups by phase in the order phases first appear; no phase is the whole process", () => {
    const groups = byPhase([q("1", "Plan"), q("2", ""), q("3", "Plan"), q("4", "Close out")]);
    expect(groups.map((g) => [g.phase, g.questions.map((x) => x.id)])).toEqual([
      ["Plan", ["1", "3"]],
      [WHOLE_PROCESS, ["2"]],
      ["Close out", ["4"]],
    ]);
  });

  it("writes Markdown for the offline session, answered ones marked", () => {
    const text = questionsMarkdown(
      [q("1", "Plan", "open", "contested", "Draft load plan"), q("2", "", "answered")],
      "Load control",
      "v0.2",
    );
    expect(text).toBe(
      [
        "# Validation questions: Load control",
        "",
        "Draft v0.2. 1 of 2 questions open. For the session with the people who do the work.",
        "",
        "## Plan",
        "",
        "1. Question 1? (step: Draft load plan) · Contested",
        "",
        "## Whole process",
        "",
        "1. Question 2? · Gap [answered]",
        "",
      ].join("\n"),
    );
  });

  it("names the file after the draft", () => {
    expect(questionsFileName("v0.2")).toBe("validation-questions-v0-2.md");
    expect(questionsFileName("")).toBe("validation-questions-draft.md");
  });
});
