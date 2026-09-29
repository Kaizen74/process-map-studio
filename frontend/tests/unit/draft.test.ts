import { describe, expect, it } from "vitest";
import type { JobStage, Readiness } from "../../src/api/types";
import {
  AI_CALL_STATUS,
  STAGE_LOOK,
  aiStageName,
  draftChecklist,
  durationLabel,
  elapsedLabel,
  groupDigits,
  stageElapsedMs,
} from "../../src/lib/draft";

const stage = (extra: Partial<JobStage>): JobStage => ({
  id: "read",
  name: "Reading the documents",
  status: "waiting",
  started_at: null,
  finished_at: null,
  ...extra,
});

describe("elapsed time", () => {
  it.each([
    [0, "0 s"],
    [45_900, "45 s"],
    [125_000, "2 min 05 s"],
    [3_720_000, "1 h 02 min"],
    [-5, "0 s"],
  ])("%i ms reads %s", (ms, label) => expect(elapsedLabel(ms)).toBe(label));

  it("measures a finished stage from start to finish, a running one to now", () => {
    const start = "2026-09-26T10:00:00+00:00";
    expect(stageElapsedMs(stage({ started_at: start, finished_at: "2026-09-26T10:00:30+00:00" }), 0)).toBe(30_000);
    expect(stageElapsedMs(stage({ started_at: start }), Date.parse(start) + 5_000)).toBe(5_000);
    expect(stageElapsedMs(stage({}), Date.now())).toBeNull();
    expect(stageElapsedMs(stage({ started_at: "not a time" }), Date.now())).toBeNull();
  });
});

describe("token counts", () => {
  it.each([
    [0, "0"],
    [999, "999"],
    [15400, "15,400"],
    [1234567, "1,234,567"],
  ])("%i reads %s", (n, text) => expect(groupDigits(n)).toBe(text));
});

describe("stage looks", () => {
  it("gives every status its own shape and text, never colour alone", () => {
    const looks = Object.values(STAGE_LOOK);
    expect(new Set(looks.map((l) => l.shape)).size).toBe(looks.length);
    expect(new Set(looks.map((l) => l.label)).size).toBe(looks.length);
  });
});

describe("draft checklist", () => {
  const ready: Readiness = {
    key_set: true,
    transcripts_ready: true,
    documents_ready: true,
    speakers_unmapped: 0,
    draft_exists: false,
    blockers_count: 0,
    nav: {} as Readiness["nav"],
    nav_counts: {},
    next_step: "draft",
    missing: [],
    ready_to_draft: true,
  };

  it("is all done when ready", () => {
    expect(draftChecklist(ready).every((item) => item.done)).toBe(true);
  });

  it("doesn't call speakers mapped before any transcript is read", () => {
    const items = draftChecklist({ ...ready, transcripts_ready: false, key_set: false });
    expect(items.filter((i) => !i.done).map((i) => i.key)).toEqual(["key", "transcript", "speakers"]);
    expect(items.find((i) => i.key === "key")?.to).toBe("settings");
  });

  it("shows unmapped speakers as a to-do", () => {
    const items = draftChecklist({ ...ready, speakers_unmapped: 2 });
    expect(items.filter((i) => !i.done).map((i) => i.key)).toEqual(["speakers"]);
  });
});

describe("AI usage wording", () => {
  it("names stages in plain words and keeps unknown IDs", () => {
    expect(aiStageName("S0_ocr_page")).toBe("Reading a scanned page");
    expect(aiStageName("S3b_verify")).toBe("Independent verification of a step");
    expect(aiStageName("S9_new")).toBe("S9_new");
  });

  it("says in plain words how each call ended", () => {
    expect(AI_CALL_STATUS).toEqual({
      ok: "OK",
      error: "Failed",
      mock: "Test answer",
      invalid: "Wrong format",
      repaired: "Repaired",
      truncated: "Cut off",
      refused: "Declined",
    });
  });

  it.each([
    [850, "850 ms"],
    [14_200, "14.2 s"],
  ])("%i ms reads %s", (ms, text) => expect(durationLabel(ms)).toBe(text));
});
