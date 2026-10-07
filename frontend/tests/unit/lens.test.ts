import { describe, expect, it } from "vitest";
import {
  LENSES,
  durationText,
  isLens,
  lensLine,
  longestStep,
  markersFor,
  nodeName,
  type Lens,
} from "../../src/lib/lens";
import { routeLine } from "../../src/lib/exceptions";
import type { GraphElement } from "../../src/lib/mapTypes";
import { SAMPLE, elementByLabel } from "../sampleMap";

const STATES = ["corroborated", "documented_only", "practiced_only", "contested", "trace_contradicted", "not_assessed"];
const REVIEWS = ["draft", "confirmed", "edited", "added", "rejected"];
const KINDS = ["activity", "decision", "approval", "start", "end"] as const;
const LENS_VALUES = LENSES.map((l) => l.value);

function step(extra: Partial<GraphElement> = {}): GraphElement {
  return { ...elementByLabel("Load and return LIR"), ...extra };
}

describe("lens lines (PRD §5.5)", () => {
  it("plain: the duration in mono, or 'No time stated' in danger text", () => {
    expect(lensLine(elementByLabel("Draft load plan"), "plain")).toEqual({ kind: "text", text: "~20 min", danger: false });
    // V2: where the views differ on the step (A.9 variants), the active view's time is shown.
    expect(lensLine(step({ variants: null }), "plain")).toEqual({ kind: "text", text: "~40 min + 15 wait", danger: false });
    expect(lensLine(step(), "plain")).toEqual({
      kind: "text",
      text: "Up to fifteen minutes' wait for the report",
      danger: false,
    });
    expect(lensLine(elementByLabel("Issue load sheet"), "plain")).toEqual({
      kind: "text",
      text: "No time stated",
      danger: true,
    });
    expect(lensLine(elementByLabel("Special loads OK?"), "plain")).toEqual({ kind: "none" }); // decisions take no time
    expect(durationText(null, 15)).toBe("15 min wait");
  });

  it("source state: the state's glyph for every state", () => {
    for (const state of STATES) {
      expect(lensLine(step({ source_state: state }), "source_state")).toEqual({ kind: "state", state });
    }
    expect(lensLine(step({ source_state: "unknown" }), "source_state")).toEqual({ kind: "state", state: "not_assessed" });
  });

  it("confidence: bar and two decimals, coral and danger below 0.60", () => {
    expect(lensLine(elementByLabel("Draft load plan"), "confidence")).toEqual({
      kind: "confidence",
      value: 0.85,
      text: "0.85",
      low: false,
      bar: 39,
    });
    expect(lensLine(step({ confidence: 0.45 }), "confidence")).toMatchObject({ text: "0.45", low: true });
    expect(lensLine(step({ confidence: null }), "confidence")).toEqual({ kind: "none" });
  });

  it("time: work and wait bars scaled to the longest step, with the minutes", () => {
    const longest = longestStep(SAMPLE.graph.elements);
    expect(longest).toBe(55);
    expect(lensLine(step(), "time", longest)).toEqual({ kind: "time", text: "40 + 15", work: 33, wait: 13 });
    expect(lensLine(elementByLabel("Issue load sheet"), "time", longest)).toMatchObject({ text: "No time stated" });
  });

  it("start and end have no lens line", () => {
    for (const lens of LENS_VALUES) {
      expect(lensLine(elementByLabel("Flight scheduled"), lens)).toEqual({ kind: "none" });
    }
  });

  it("knows its lenses", () => {
    // V2: + Work type; X3 (2026-10-06, Eric's request): + Exceptions.
    expect(LENS_VALUES).toEqual(["plain", "source_state", "confidence", "time", "work_type", "exceptions"]);
    expect(isLens("time")).toBe(true);
    expect(isLens("colour")).toBe(false);
  });
});

describe("Exceptions lens (X3)", () => {
  const routes = new Map(SAMPLE.exceptions.done.steps.map((s) => [s.element_id, s]));
  const line = (label: string) => lensLine(elementByLabel(label), "exceptions", 0, "done", routes);

  it("says, from the backend's report, which route each step of the sample is on (As done)", () => {
    expect(line("Draft load plan")).toEqual({ kind: "text", text: "Usual route", danger: false });
    expect(line("Resolve or offload")).toEqual({ kind: "text", text: "Exception", danger: false });
    expect(line("Approve deviation")).toEqual({ kind: "text", text: "Exception", danger: false });
    expect(line("Read report at aircraft")).toEqual({ kind: "text", text: "Workaround", danger: false });
    expect(line("Busy wave?")).toEqual({ kind: "text", text: "Usual route", danger: false });
  });

  it("shows nothing until the report has arrived, and nothing for start and end", () => {
    expect(lensLine(elementByLabel("Draft load plan"), "exceptions")).toEqual({ kind: "none" });
    const start = SAMPLE.graph.elements.find((e) => e.kind === "start") as GraphElement;
    expect(lensLine(start, "exceptions", 0, "done", routes)).toEqual({ kind: "none" });
  });

  it("names every kind of route in one short word that fits under a node", () => {
    const base = { element_id: "x", label: "X", workaround: false, condition: "on a busy wave" };
    expect(routeLine({ ...base, route: "variation" })).toBe("Variation");
    expect(routeLine({ ...base, route: "exception" })).toBe("Exception");
    expect(routeLine({ ...base, route: "usual" })).toBe("Usual route");
    expect(routeLine({ ...base, route: "usual", workaround: true })).toBe("Workaround");
    expect(routeLine({ ...base, route: "exception", workaround: true })).toBe("Workaround");
  });
});

describe("markers (PRD §5.5, constraint 17)", () => {
  it("never more than three, and no lens adds one: every lens × state × review × kind", () => {
    for (const kind of KINDS) {
      for (const state of STATES) {
        for (const review of REVIEWS) {
          for (const hasImages of [false, true]) {
            const element = step({
              kind,
              source_state: state,
              review_status: review,
              constraints: [{ text: "x", provenance: "O", cause_type: null, is_key: true }],
            });
            const markers = markersFor(element, { hasImages });
            expect(markers.length).toBeLessThanOrEqual(3);
            for (const lens of LENS_VALUES as Lens[]) {
              lensLine(element, lens, 55); // choosing a lens changes nothing about the markers
              expect(markersFor(element, { hasImages })).toEqual(markers);
            }
          }
        }
      }
    }
  });

  it("shows the key constraint, images and the unreviewed outline only when they apply", () => {
    expect(markersFor(step(), { hasImages: false })).toEqual(["key_constraint", "unreviewed"]);
    expect(markersFor(step({ review_status: "confirmed", constraints: [] }), { hasImages: true })).toEqual(["images"]);
    expect(markersFor(elementByLabel("Flight scheduled"), { hasImages: true })).toEqual([]);
  });
});

describe("spoken node names (PRD §5.10)", () => {
  it("say kind, label, lane, source state and review status", () => {
    expect(nodeName(elementByLabel("Draft load plan"), "Load controller")).toBe(
      "Activity, Draft load plan, Load controller, corroborated, unreviewed",
    );
    expect(nodeName(elementByLabel("Flight scheduled"), "")).toBe("Start, Flight scheduled");
  });
});
