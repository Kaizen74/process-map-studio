import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DraftState, Job, JobStage, RejectedClaims } from "../../src/api/types";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

const PATH = "/engagements/e1/draft";
const READY = {
  ...READINESS,
  key_set: true,
  transcripts_ready: true,
  documents_ready: true,
  missing: [] as string[],
  ready_to_draft: true,
};
const NAMES: [string, string][] = [
  ["read", "Reading the documents"],
  ["extract", "Extracting steps from each source"],
  ["check", "Checking every quote against your documents"],
  ["compare", "Comparing sources"],
  ["verify", "Independent verification"],
  ["build", "Building the map"],
  ["questions", "Writing validation questions"],
];

function stages(statuses: JobStage["status"][]): JobStage[] {
  return NAMES.map(([id, name], i) => {
    const status = statuses[i] ?? "later";
    const started = status === "waiting" || status === "later" ? null : "2026-09-26T10:00:00+00:00";
    const finished = status === "done" || status === "failed" ? "2026-09-26T10:01:05+00:00" : null;
    return { id, name, status, started_at: started, finished_at: finished };
  });
}

function job(extra: Partial<Job> = {}): Job {
  return {
    id: "j1",
    engagement_id: "e1",
    type: "draft",
    target_id: "v1",
    status: "running",
    stage: "Extracting steps from each source",
    progress: 0.4,
    message: "",
    error: "",
    usage: { calls: 3, input_tokens: 15000, output_tokens: 400 },
    claims: { verified: 12, rejected: 1 },
    stages: stages(["done", "running", "running", "later", "later", "later", "later"]),
    created_at: "2026-09-26T10:00:00+00:00",
    ...extra,
  };
}

const VERSION = { id: "v1", engagement_id: "e1", label: "v0.1", state: "draft" as const, created_at: "2026-09-26T10:02:00+00:00" };
const DONE: DraftState = {
  job: job({ status: "done", progress: 1, stages: stages(["done", "done", "done"]), message: "Draft v0.1 is ready" }),
  version: VERSION,
  summary: { steps: 8, needs_check: 1, verified: 21, rejected: 2, open_questions: 5, scrubbed: 1 },
};
const REJECTED: RejectedClaims = {
  items: [
    {
      id: "c1",
      claim_text: "T1: The Load controller builds the plan.",
      source_id: "s2",
      source_name: "interview_transcript.txt",
      anchor: "",
      reason: "cites a passage that wasn't provided",
      guardrail: "G3",
      stage: "S1",
      passage_available: false,
      segment_id: null,
    },
    {
      id: "c2",
      claim_text: "T3: The plan takes 30 min.",
      source_id: "s2",
      source_name: "interview_transcript.txt",
      anchor: "08:12",
      reason: "number not found in cited text: 30",
      guardrail: "G5",
      stage: "S1",
      passage_available: true,
      segment_id: "g2",
    },
  ],
  total: 2,
  scrub_count: 1,
  instruction_like_count: 1,
};

function draftApi(state: DraftState, extra: Parameters<typeof fakeApi>[0] = {}, readiness = READY) {
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: readiness }),
    "GET /api/engagements/e1/draft": () => ({ body: state }),
    "GET /api/versions/v1/rejected-claims": () => ({ body: REJECTED }),
    ...extra,
  });
}

const EMPTY: DraftState = { job: null, version: null, summary: null };

describe("Draft screen", () => {
  it("shows what is missing before drafting, with links to fix it", async () => {
    draftApi(EMPTY, {
      "POST /api/engagements/e1/draft": () => ({
        status: 409,
        body: {
          error: {
            code: "CONFLICT",
            message: "The draft can't start yet: Add your Claude API key in Settings.",
            details: { missing: READINESS.missing },
          },
        },
      }),
    }, READINESS);
    renderApp(PATH);
    const checklist = await screen.findByRole("region", { name: "Before drafting" });
    expect(within(checklist).getByText("0 of 3 ready.")).toBeInTheDocument();
    expect(within(checklist).getByRole("link", { name: "Add it in Settings" })).toHaveAttribute("href", "/settings");
    expect(within(checklist).getAllByRole("link", { name: "Go to Sources" })[0]).toHaveAttribute(
      "href",
      "/engagements/e1/sources",
    );
    expect(within(checklist).getByText("Add an interview transcript")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create draft map" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The draft can't start yet: Add your Claude API key");
  });

  it("starts a draft and shows the stages while it runs", async () => {
    let state: DraftState = EMPTY;
    const api = draftApi(EMPTY, {
      "GET /api/engagements/e1/draft": () => ({ body: state }),
      "POST /api/engagements/e1/draft": () => {
        state = { ...EMPTY, job: job() };
        return { status: 202, body: { job_id: "j1" } };
      },
    });
    renderApp(PATH);
    fireEvent.click(await screen.findByRole("button", { name: "Create draft map" }));
    const stepper = await screen.findByRole("list", { name: "Drafting stages" });
    expect(api.calls.some((c) => c.key === "POST /api/engagements/e1/draft")).toBe(true);
    const items = within(stepper).getAllByRole("listitem");
    expect(items).toHaveLength(7);
    expect(items[0]).toHaveTextContent("Reading the documents");
    expect(items[0]).toHaveTextContent("Done · 1 min 05 s");
    expect(items[1]).toHaveTextContent("Running");
    expect(items[6]).toHaveTextContent("Later build phase");
    expect(screen.getByRole("progressbar", { name: "Drafting progress" })).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByText("Claims verified").nextElementSibling).toHaveTextContent("12");
    expect(screen.getByText("Tokens used so far").nextElementSibling).toHaveTextContent("15,400");
    expect(screen.queryByRole("button", { name: "Create draft map" })).not.toBeInTheDocument();
  });

  it("says when the independent verification was switched off", async () => {
    draftApi({ ...EMPTY, job: job({ stages: stages(["done", "done", "done", "done", "skipped", "running"]) }) });
    renderApp(PATH);
    const stepper = await screen.findByRole("list", { name: "Drafting stages" });
    expect(within(stepper).getAllByRole("listitem")[4]).toHaveTextContent("Switched off in Settings");
  });

  it("explains a failed draft and offers Try again and Copy details", async () => {
    const failed = job({
      status: "failed",
      error: "Claude's answer for 'Extracting steps from each source' didn't match the expected format twice. Nothing was saved.",
      stages: stages(["done", "failed", "failed"]),
    });
    const api = draftApi({ ...EMPTY, job: failed }, {
      "POST /api/engagements/e1/draft": () => ({ status: 202, body: { job_id: "j2" } }),
    });
    renderApp(PATH);
    expect(await screen.findByText("The draft couldn't be finished")).toBeInTheDocument();
    expect(screen.getByText(/Nothing was saved/)).toBeInTheDocument();
    const stepper = screen.getByRole("list", { name: "Drafting stages" });
    expect(within(stepper).getAllByText(/Failed/)).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Copy details" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create draft map" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() =>
      expect(api.calls.filter((c) => c.key === "POST /api/engagements/e1/draft")).toHaveLength(1),
    );
  });

  it("summarises a finished draft and lists the rejected claims", async () => {
    draftApi(DONE);
    renderApp(PATH);
    const summary = await screen.findByRole("region", { name: "Draft v0.1" });
    expect(within(summary).getByText("Steps drafted").nextElementSibling).toHaveTextContent("8");
    expect(within(summary).getByText("Needs check").nextElementSibling).toHaveTextContent("1");
    expect(within(summary).getByText("Open questions").nextElementSibling).toHaveTextContent("5");
    expect(within(summary).getByText(/Built from 21 checked claims/)).toBeInTheDocument();
    expect(within(summary).getByRole("link", { name: "Start reviewing" })).toHaveAttribute(
      "href",
      "/engagements/e1/review",
    );
    expect(screen.getByRole("button", { name: "Draft again from sources" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Before drafting" })).not.toBeInTheDocument();

    const register = await screen.findByRole("region", { name: "Rejected claims (2)" });
    expect(within(register).getByText(/2 claims failed a check/)).toBeInTheDocument();
    expect(within(register).getByText(/1 name replaced by roles; 1 instruction-like passage/)).toBeInTheDocument();
    expect(within(register).getByText("number not found in cited text: 30")).toBeInTheDocument();
    expect(within(register).getByText("G5 · S1")).toBeInTheDocument();
    expect(within(register).getByText("Passage missing")).toBeInTheDocument();
    expect(within(register).getByRole("link", { name: "Open source" })).toHaveAttribute(
      "href",
      "/engagements/e1/sources?source=s2",
    );
    expect(within(register).getByText("T3: The plan takes 30 min.").tagName).toBe("S");
  });

  it("allows a draft from interviews alone and shows its signal strength", async () => {
    const limited = {
      level: "limited" as const,
      label: "Limited",
      score: 1,
      detail: "Built from interviews only. Every step is 'practiced only': confirm it with a document or another SME before relying on it.",
    };
    const interviewsOnly = {
      ...READY,
      documents_ready: false,
      recommended: ["Add a process document such as an SOP or manual"],
      signal: limited,
    };
    draftApi(EMPTY, {}, interviewsOnly);
    const { container } = renderApp(PATH);
    const checklist = await screen.findByRole("region", { name: "Before drafting" });
    expect(within(checklist).getByText("3 of 3 ready.")).toBeInTheDocument();
    expect(within(checklist).getByText("Recommended")).toBeInTheDocument();
    expect(within(checklist).getByText("Recommended, not required:")).toBeInTheDocument();
    expect(within(checklist).getByText("Add a process document such as an SOP or manual")).toBeInTheDocument();
    const meter = container.querySelector(".signal");
    expect(meter).toHaveTextContent("Signal strength: Limited (1 of 3)");
    expect(meter).toHaveTextContent(/confirm it with a document or another SME/);
    expect(meter?.querySelectorAll(".signal__bar--on")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Create draft map" })).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("shows the checklist again when a draft exists but something is missing now", async () => {
    draftApi(DONE, {}, { ...READY, documents_ready: false, missing: ["Add a process document"], ready_to_draft: false });
    renderApp(PATH);
    const checklist = await screen.findByRole("region", { name: "Before drafting" });
    expect(within(checklist).getByText("Add a process document")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Draft v0.1" })).toBeInTheDocument();
  });

  it("shows the finished draft's signal strength from its version", async () => {
    const strong = { level: "strong" as const, label: "Strong", score: 3, detail: "Interviews and a procedure agree or differ in the open." };
    draftApi(DONE, {
      "GET /api/engagements/e1/versions": () => ({ body: [{ ...VERSION, published_at: null, published_by: null, parent_version_id: null, signal: strong }] }),
    });
    renderApp(PATH);
    const summary = await screen.findByRole("region", { name: "Draft v0.1" });
    await waitFor(() => expect(summary.querySelector(".signal")).toHaveTextContent("Signal strength: Strong (3 of 3)"));
    expect(summary.querySelectorAll(".signal__bar--on")).toHaveLength(3);
  });

  it("explains a draft with no steps instead of offering to review it", async () => {
    draftApi({ ...DONE, summary: { steps: 0, needs_check: 0, verified: 0, rejected: 2, open_questions: 0, scrubbed: 0 } });
    renderApp(PATH);
    const summary = await screen.findByRole("region", { name: "Draft v0.1" });
    expect(within(summary).getByRole("status")).toHaveTextContent(
      "No steps could be drafted: nothing in these sources described a step that passed every check.",
    );
    expect(within(summary).getByRole("status")).toHaveTextContent(/Add a process document or another interview/);
    expect(within(summary).queryByRole("link", { name: "Start reviewing" })).toBeNull();
    // Eric, 2026-10-19: the map still has its start and end, so he can add the steps himself.
    expect(within(summary).getByRole("status")).toHaveTextContent(/The map still shows where the process starts and ends/);
    expect(within(summary).getByRole("link", { name: "Review" })).toHaveAttribute("href", "/engagements/e1/review");
  });

  it("says what a refresh drafted differently among the steps not yet reviewed", async () => {
    draftApi({
      ...DONE,
      job: { ...(DONE.job as Job), type: "refresh" },
      last_refresh: {
        kept: 2,
        new_steps: ["Approve deviation"],
        no_longer_drafted: ["Brief the crew"],
        renamed: [{ before: "Loads OK?", after: "Special loads OK?" }],
      },
    });
    renderApp(PATH);
    const summary = await screen.findByRole("region", { name: "Draft v0.1" });
    const note = within(summary).getByRole("region", { name: "What the refresh changed" });
    expect(note).toHaveTextContent("The 2 steps you reviewed stayed exactly as they were.");
    expect(within(note).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "New: Approve deviation",
      "No longer drafted: Brief the crew",
      "Renamed: Loads OK? → Special loads OK?",
    ]);
    expect(note).toHaveTextContent("Look at these on the map before you confirm them.");
    expect(await seriousViolations(document.body)).toEqual([]);
  });

  it("says a refresh changed nothing among unreviewed steps, and shows no note after a plain draft", async () => {
    draftApi({ ...DONE, last_refresh: { kept: 0, new_steps: [], no_longer_drafted: [], renamed: [] } });
    const { unmount } = renderApp(PATH);
    const note = await screen.findByRole("region", { name: "What the refresh changed" });
    expect(note).toHaveTextContent("You hadn't reviewed any steps, so every step was drafted again.");
    expect(note).toHaveTextContent("The steps you hadn't reviewed came out the same as before.");
    expect(within(note).queryByRole("list")).toBeNull();
    unmount();
    draftApi(DONE);
    renderApp(PATH);
    await screen.findByRole("region", { name: "Draft v0.1" });
    expect(screen.queryByRole("region", { name: "What the refresh changed" })).toBeNull();
  });

  it("says so when no claims were rejected", async () => {
    draftApi(DONE, {
      "GET /api/versions/v1/rejected-claims": () => ({
        body: { items: [], total: 0, scrub_count: 0, instruction_like_count: 0 },
      }),
    });
    renderApp(PATH);
    expect(await screen.findByText(/No claims were rejected/)).toBeInTheDocument();
  });

  it("shows a plain error when the draft can't be loaded", async () => {
    draftApi(EMPTY, {
      "GET /api/engagements/e1/draft": () => ({
        status: 500,
        body: { error: { code: "IO", message: "The database couldn't be read.", details: {} } },
      }),
    });
    renderApp(PATH);
    expect(await screen.findByText("The draft couldn't be loaded")).toBeInTheDocument();
    expect(screen.getByText("The database couldn't be read.")).toBeInTheDocument();
  });

  it.each([
    ["before drafting", EMPTY],
    ["while drafting", { ...EMPTY, job: job() }],
    ["after drafting", DONE],
  ])("has no serious or critical accessibility violations %s", async (_label, state) => {
    draftApi(state);
    const { container } = renderApp(PATH);
    await screen.findByRole("heading", { name: "Draft" });
    await waitFor(() => expect(container.querySelector("[aria-busy='true']")).toBeNull());
    expect(await seriousViolations(container)).toEqual([]);
  });
});
