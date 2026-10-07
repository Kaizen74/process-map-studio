import { describe, expect, it } from "vitest";
import {
  exitText,
  frequencyText,
  summaryText,
  type ExceptionQuestion,
  type ExceptionReport,
  type ExceptionRoute,
  type ExceptionStep,
  type ExceptionSummary,
  type ReworkLoop,
  type RouteExit,
  type Workaround,
} from "../../src/lib/exceptions";
import type { AnswerQuote, CapabilityNote, GlossaryEntry, StoryEntry } from "../../src/lib/mapTypes";
import { SAMPLE } from "../sampleMap";

// Every field of each type, exactly (`satisfies` refuses a missing or an extra one), so the
// backend's real output (the sample, written by the backend test) can be compared field by field.
const REPORT = { view: 1, summary: 1, steps: 1, routes: 1, loops: 1, workarounds: 1, questions: 1 } satisfies Record<keyof ExceptionReport, 1>; // prettier-ignore
const SUMMARY = { steps: 1, usual_steps: 1, exception_steps: 1, variation_steps: 1, off_usual_share: 1, routes: 1, rework_loops: 1, workarounds: 1, extra_handoffs: 1, frequency_stated: 1 } satisfies Record<keyof ExceptionSummary, 1>; // prettier-ignore
const STEP = { element_id: 1, label: 1, route: 1, workaround: 1, condition: 1 } satisfies Record<keyof ExceptionStep, 1>; // prettier-ignore
const ROUTE = { id: 1, kind: 1, from_element_id: 1, from_label: 1, condition: 1, element_ids: 1, labels: 1, lanes: 1, exits: 1, handoffs: 1, frequency: 1, stated_reason: 1 } satisfies Record<keyof ExceptionRoute, 1>; // prettier-ignore
const EXIT = { kind: 1, element_id: 1, label: 1, edge_label: 1 } satisfies Record<keyof RouteExit, 1>; // prettier-ignore
const LOOP = { from_element_id: 1, from_label: 1, to_element_id: 1, to_label: 1, label: 1 } satisfies Record<keyof ReworkLoop, 1>; // prettier-ignore
const WORKAROUND = { element_id: 1, label: 1, lane: 1, condition: 1, stated_reason: 1, frequency: 1, basis: 1 } satisfies Record<keyof Workaround, 1>; // prettier-ignore
const QUESTION = { question_id: 1, wording: 1, about: 1 } satisfies Record<keyof ExceptionQuestion, 1>; // prettier-ignore
const ANSWER = { quote: 1, account_type: 1, account_cue: 1, stated_reason: 1, variation_condition: 1, frequency: 1, source_id: 1, segment_id: 1, anchor: 1, question_id: 1, question: 1 } satisfies Record<keyof AnswerQuote, 1>; // prettier-ignore

const STORY = { label: 1, fragment_type: 1, signifiers: 1, frequency: 1, single_account: 1, quote: 1, source_id: 1, segment_id: 1, anchor: 1, steps: 1 } satisfies Record<keyof StoryEntry, 1>; // prettier-ignore
const TERM = { term: 1, plain_meaning: 1, steps: 1, source_id: 1, segment_id: 1, anchor: 1 } satisfies Record<keyof GlossaryEntry, 1>; // prettier-ignore
const NOTE = { kind: 1, dimension: 1, text: 1, cause_type: 1, steps: 1, quote: 1, source_id: 1, segment_id: 1, anchor: 1 } satisfies Record<keyof CapabilityNote, 1>; // prettier-ignore

const keys = (o: object) => Object.keys(o).sort();

describe("the frontend's types match what the backend sends (X4 alignment)", () => {
  it("every field of the exceptions report, in both views", () => {
    for (const report of [SAMPLE.exceptions.done, SAMPLE.exceptions.documented]) {
      expect(keys(report)).toEqual(keys(REPORT));
      expect(keys(report.summary)).toEqual(keys(SUMMARY));
      report.steps.forEach((s) => expect(keys(s)).toEqual(keys(STEP)));
      report.routes.forEach((r) => {
        expect(keys(r)).toEqual(keys(ROUTE));
        r.exits.forEach((x) => expect(keys(x)).toEqual(keys(EXIT)));
      });
      report.loops.forEach((l) => expect(keys(l)).toEqual(keys(LOOP)));
      report.workarounds.forEach((w) => expect(keys(w)).toEqual(keys(WORKAROUND)));
      report.questions.forEach((q) => expect(keys(q)).toEqual(keys(QUESTION)));
    }
    expect(SAMPLE.exceptions.done.routes.length).toBeGreaterThan(0); // so the loops above ran
  });

  it("every field of the Registers lists made from the interviews (P9u)", () => {
    const { stories, glossary } = SAMPLE.lists;
    const notes = SAMPLE.lists["capability-notes"];
    expect(stories.length * glossary.length * notes.length).toBeGreaterThan(0);
    stories.forEach((s) => expect(keys(s)).toEqual(keys(STORY)));
    glossary.forEach((g) => expect(keys(g)).toEqual(keys(TERM)));
    notes.forEach((n) => expect(keys(n)).toEqual(keys(NOTE)));
  });

  it("every field of an interview answer, with how often (X1)", () => {
    const answers = Object.values(SAMPLE.elements).flatMap((e) => e.answers ?? []);
    expect(answers.length).toBeGreaterThan(0);
    answers.forEach((a) => expect(keys(a)).toEqual(keys(ANSWER)));
  });
});

describe("plain words (X3)", () => {
  it("summarises the sample As done in one line of facts", () => {
    expect(summaryText(SAMPLE.exceptions.done.summary)).toBe(
      "3 of 9 steps (33%) are off the usual route: 2 on exception routes, 1 variation. 2 rework loops; 1 workaround. The exception routes add 4 hand-overs.",
    );
  });

  it("says when everything is on the usual route, and when a view has no steps", () => {
    const quiet: ExceptionSummary = { ...SAMPLE.exceptions.documented.summary, rework_loops: 0 };
    expect(summaryText(quiet)).toBe(
      "All 6 steps are on the usual route; no exception routes, rework loops or workarounds.",
    );
    expect(summaryText({ ...quiet, steps: 0 })).toBe("No steps in this view yet.");
    expect(summaryText(SAMPLE.exceptions.documented.summary)).toBe(
      "0 of 6 steps (0%) are off the usual route: 0 on exception routes, 0 variations. 1 rework loop; 0 workarounds.",
    );
  });

  it("says how a route ends and how often it happens", () => {
    const exit = { element_id: "x", label: "Draft load plan", edge_label: "Re-plan" };
    expect(exitText({ ...exit, kind: "loops_back" })).toBe("goes back to Draft load plan (Re-plan)");
    expect(exitText({ ...exit, kind: "rejoins", edge_label: "" })).toBe("rejoins the usual route at Draft load plan");
    expect(exitText({ ...exit, kind: "ends" })).toBe("ends the process");
    expect(frequencyText("")).toBe("How often: not stated yet");
    expect(frequencyText("maybe once a month")).toBe("How often: maybe once a month");
  });
});
