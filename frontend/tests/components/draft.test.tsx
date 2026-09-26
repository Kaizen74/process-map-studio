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
  summary: { verified: 21, rejected: 2, open_questions: 3, scrubbed: 1 },
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
    expect(within(checklist).getByText("0 of 4 ready.")).toBeInTheDocument();
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
    expect(within(summary).getByText("Claims verified").nextElementSibling).toHaveTextContent("21");
    expect(within(summary).getByText("Open questions").nextElementSibling).toHaveTextContent("3");
    expect(screen.getByRole("button", { name: "Draft again from sources" })).toBeInTheDocument();

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
