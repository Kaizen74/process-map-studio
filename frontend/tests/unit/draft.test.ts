import { describe, expect, it } from "vitest";
import type { DraftEstimate, JobStage, Readiness } from "../../src/api/types";
import {
  AI_CALL_STATUS,
  STAGE_LOOK,
  aiStageName,
  checklistSummary,
  draftChecklist,
  durationLabel,
  elapsedLabel,
  estimateLines,
  groupDigits,
  stageElapsedMs,
  usd,
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

  it("needs a transcript or a process document; speakers count only once a transcript is read", () => {
    const items = draftChecklist({ ...ready, transcripts_ready: false, documents_ready: false, key_set: false });
    expect(items.filter((i) => !i.done).map((i) => i.key)).toEqual(["key", "source", "transcript", "document"]);
    expect(items.filter((i) => i.required).map((i) => i.key)).toEqual(["key", "source"]);
    expect(items.find((i) => i.key === "key")?.to).toBe("settings");
    expect(checklistSummary(items)).toBe("0 of 2 ready.");
  });

  it("documents alone are enough to draft (Eric, 2026-10-20); the interview is recommended", () => {
    const items = draftChecklist({ ...ready, transcripts_ready: false });
    expect(items.find((i) => i.key === "source")).toMatchObject({ done: true, required: true });
    expect(items.find((i) => i.key === "transcript")).toMatchObject({ done: false, required: false });
    expect(items.map((i) => i.key)).not.toContain("speakers");
    expect(checklistSummary(items)).toBe("2 of 2 ready.");
  });

  it("an interview alone is enough to draft; a process document is recommended", () => {
    const items = draftChecklist({ ...ready, documents_ready: false });
    const document = items.find((i) => i.key === "document");
    expect(document).toMatchObject({ done: false, required: false });
    expect(items.filter((i) => i.required).map((i) => i.key)).toEqual(["key", "source", "speakers"]);
    expect(checklistSummary(items)).toBe("3 of 3 ready.");
    expect(checklistSummary(draftChecklist({ ...ready, key_set: false }))).toBe("2 of 3 ready.");
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

describe("cost estimate lines (deep review item 5)", () => {
  const base: DraftEstimate = {
    sources: 1,
    characters: 1000,
    input_tokens: 1000,
    output_tokens: 500,
    cost_usd: 0.014,
    basis: "measured",
    drafts_measured: 1,
    model: "claude-opus-5-5",
    prices_checked_on: "2026-01-02",
    limit_usd: null,
    over_limit: false,
  };

  it("writes dollars to the cent, with thousands separated and tiny amounts named", () => {
    expect(usd(0.67)).toBe("US$0.67");
    expect(usd(2.999)).toBe("US$3.00");
    expect(usd(1234.5)).toBe("US$1,234.50");
    expect(usd(0.004)).toBe("less than US$0.01");
    expect(usd(0)).toBe("less than US$0.01");
  });

  it("names the basis, the source count and the price date as written", () => {
    expect(estimateLines(base)).toEqual({
      cost: "Estimated cost: about US$0.01 for 1 source (based on your last 1 real draft; prices checked 2 Jan 2026).",
      limit: null,
    });
  });

  it("adds the limit sentence only when the estimate is above it", () => {
    expect(estimateLines({ ...base, limit_usd: 5 }).limit).toBeNull();
    expect(estimateLines({ ...base, cost_usd: 7, limit_usd: 5, over_limit: true }).limit).toBe(
      "That is above your limit of US$5.00, so the draft won't start. Raise the limit in Settings, or draft from fewer sources.",
    );
  });
});
