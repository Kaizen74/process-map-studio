import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftState } from "../../src/api/types";
import type { Graph } from "../../src/lib/mapTypes";
import type { AuditEntry, LintReport, MergeProposal, Question, RejectedClaims } from "../../src/lib/reviewTypes";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp, type Handler } from "../renderApp";
import { SAMPLE, elementByLabel } from "../sampleMap";

const VID = SAMPLE.graph.version.id;
const PATH = "/engagements/e1/review";
const PLAN = elementByLabel("Draft load plan");
const DEVIATION = elementByLabel("Deviation in limits?");

const QUESTIONS: Question[] = [
  { id: "q1", element_id: PLAN.id, element_label: "Draft load plan", phase_id: "id-7", phase_name: "Plan",
    question: "Is the plan always drafted by T-120?", reason: "documented_only", status: "open" },
  { id: "q2", element_id: DEVIATION.id, element_label: "Deviation in limits?", phase_id: "id-9", phase_name: "Close out",
    question: "Who is accountable for approving a deviation?", reason: "contested", status: "open" },
  { id: "q3", element_id: null, element_label: "", phase_id: null, phase_name: "",
    question: "What happens when the aircraft changes?", reason: "gap", status: "answered" },
]; // prettier-ignore

const REJECTED: RejectedClaims = {
  items: [
    { id: "r1", claim_text: "The plan takes 30 min.", source_id: "id-15", source_name: "sop_LC-07.docx", anchor: "§3.1",
      reason: "number not found in cited text: 30", guardrail: "G5", stage: "S1", passage_available: true, segment_id: "id-14" },
    { id: "r2", claim_text: "Ramp signs the sheet.", source_id: "id-13", source_name: "interview_transcript.txt", anchor: "",
      reason: "cites a passage that wasn't provided", guardrail: "G3", stage: "S1", passage_available: false, segment_id: null },
  ],
  total: 2,
  scrub_count: 1,
  instruction_like_count: 0,
}; // prettier-ignore

const AUDIT: AuditEntry[] = [
  { id: "a1", at: "2026-09-27T10:02:11+00:00", actor: "Eric", action: "Confirmed step", target_type: "element",
    target_id: PLAN.id, target_label: "Draft load plan", before: null, after: null },
]; // prettier-ignore

const claim = (text: string) => ({ text, source_name: "interview_transcript.txt", anchor: "21:50", quote: text });
const MERGES: MergeProposal[] = [
  { id: "m1", proposed_label: "Resolve special loads", similarity: 0.72, decision: "pending", decided_at: null, element_id: null,
    groups: [
      { label: "Resolve or offload", kind: "activity", lane_role_name: "Airline ops", element_id: elementByLabel("Resolve or offload").id,
        claims: [claim("Airline ops resolves it")] },
      { label: "Offload the item", kind: "activity", lane_role_name: "Ramp", element_id: null, claims: [claim("We offload it")] },
    ] },
  { id: "m2", proposed_label: "Load and return LIR", similarity: 0.86, decision: "accepted", decided_at: null,
    element_id: elementByLabel("Load and return LIR").id,
    groups: [
      { label: "Load aircraft", kind: "activity", lane_role_name: "Ramp", element_id: null, claims: [claim("Ramp loads")] },
      { label: "Return the LIR", kind: "activity", lane_role_name: "Ramp", element_id: null, claims: [claim("LIR comes back")] },
    ] },
]; // prettier-ignore

const LINT: LintReport = {
  failures: [{ rule: "L4", element_id: DEVIATION.id, message: 'Decision "Deviation in limits?" needs at least two labelled exits; it has 1.' }],
  warnings: [{ rule: "L12", element_id: null, message: "The map has 4 line crossings; consider changing the lane order." }],
};

function backend(state: "draft" | "published" = "draft") {
  const graph: Graph = { ...structuredClone(SAMPLE.graph), version: { ...SAMPLE.graph.version, state } };
  const questions = structuredClone(QUESTIONS);
  const draft: DraftState = {
    job: null,
    version: { id: VID, engagement_id: "e1", label: "v0.1", state, created_at: "2026-09-27T10:00:00+00:00" },
    summary: { steps: 8, needs_check: 0, verified: 21, rejected: 2, open_questions: 2, scrubbed: 1 },
  };
  const routes: Record<string, Handler> = {
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/draft": () => ({ body: draft }),
    "GET /api/engagements/e1/sources": () => ({ body: [] }),
    [`GET /api/versions/${VID}/graph`]: () => ({ body: graph }),
    [`GET /api/versions/${VID}/layout`]: () => ({ body: SAMPLE.layout }),
    [`GET /api/versions/${VID}/questions`]: () => ({ body: questions }),
    [`GET /api/versions/${VID}/rejected-claims`]: () => ({ body: REJECTED }),
    [`GET /api/versions/${VID}/audit`]: () => ({ body: AUDIT }),
    [`GET /api/versions/${VID}/merge-proposals`]: () => ({ body: MERGES }),
    [`GET /api/versions/${VID}/lint`]: () => ({ body: LINT }),
    "POST /api/merge-proposals/m1/decision": (body) => ({ body: { ...MERGES[0], ...(body as object) } }),
    "PATCH /api/questions/q1": (body) => {
      const q = questions[0];
      if (q) q.status = (body as { status: string }).status;
      return { body: q };
    },
  };
  for (const [id, element] of Object.entries(SAMPLE.elements)) routes[`GET /api/elements/${id}`] = () => ({ body: element });
  for (const [id, page] of Object.entries(SAMPLE.segments)) {
    routes[`GET /api/sources/${id}/segments`] = () => ({ body: page });
    routes[`GET /api/sources/${id}`] = () => ({
      body: { id, kind: "sop", format: "docx", version_date: "2025-03-01", controlled_copy: true },
    });
  }
  return fakeApi(routes);
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

const tablist = () => screen.findByRole("tablist", { name: "Review workbench" });
const panel = () => screen.getByRole("complementary");

async function openTab(name: RegExp) {
  const tabs = await tablist();
  const tab = await within(tabs).findByRole("tab", { name });
  fireEvent.click(tab);
  return screen.getByRole("tabpanel");
}

describe("the workbench tabs (PRD §5.7.10)", () => {
  it("shows six tabs with their counts; the RACI matrix first; arrow keys move between them", async () => {
    backend();
    renderApp(PATH);
    const tabs = await tablist();
    await waitFor(() =>
      expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual([
        "RACI matrix",
        "Validation questions (2 open)",
        "Rejected claims (2)",
        "Audit log",
        "Merge decisions (1 waiting)",
        "Map checks (2)",
      ]),
    );
    const raci = within(tabs).getByRole("tab", { name: "RACI matrix" });
    expect(raci).toHaveAttribute("aria-selected", "true");
    expect(within(screen.getByRole("tabpanel")).getByRole("table")).toBeInTheDocument();
    fireEvent.keyDown(raci, { key: "ArrowRight" });
    expect(within(tabs).getByRole("tab", { name: /Validation questions/ })).toHaveFocus();
    fireEvent.keyDown(document.activeElement ?? raci, { key: "End" });
    expect(within(tabs).getByRole("tab", { name: /Map checks/ })).toHaveAttribute("aria-selected", "true");
  });

  it("validation questions: by phase, reason chips, Go to step, Mark answered", async () => {
    const api = backend();
    renderApp(PATH);
    const tab = await openTab(/Validation questions/);
    const plan = await within(tab).findByRole("region", { name: "Plan" });
    expect(within(plan).getByText("Is the plan always drafted by T-120?")).toBeInTheDocument();
    expect(within(plan).getByText("Documented only")).toBeInTheDocument();
    expect(within(tab).getByRole("region", { name: "Whole process" })).toHaveTextContent("Answered");
    fireEvent.click(within(plan).getByRole("button", { name: "Mark answered" }));
    await waitFor(() => expect(api.calls.some((c) => c.key === "PATCH /api/questions/q1")).toBe(true));
    expect(api.calls.find((c) => c.key === "PATCH /api/questions/q1")?.body).toEqual({ status: "answered" });
    expect(await within(plan).findByRole("button", { name: "Reopen" })).toBeInTheDocument();
    fireEvent.click(within(plan).getByRole("button", { name: "Go to Draft load plan" }));
    expect(await within(panel()).findByRole("heading", { name: "Draft load plan" })).toBeInTheDocument();
  });

  it("Copy all and Download .md give the questions as Markdown for the session", async () => {
    backend();
    const writeText = vi.fn(async () => undefined);
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
    const createObjectURL = vi.fn(() => "blob:questions");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    renderApp(PATH);
    const tab = await openTab(/Validation questions/);
    fireEvent.click(await within(tab).findByRole("button", { name: "Copy all" }));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    const text = String((writeText.mock.calls[0] as unknown[] | undefined)?.[0]);
    expect(text).toContain("# Validation questions: Load control");
    expect(text).toContain("## Plan\n\n1. Is the plan always drafted by T-120? (step: Draft load plan) · Documented only");
    expect(await screen.findByText("Questions copied. Paste them into your notes for the session.")).toBeInTheDocument();
    fireEvent.click(within(tab).getByRole("button", { name: "Download .md" }));
    expect(createObjectURL).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
    click.mockRestore();
  });

  it("rejected claims: open the passage, or add the step from it", async () => {
    backend();
    renderApp(PATH);
    const tab = await openTab(/Rejected claims/);
    expect(await within(tab).findByText("number not found in cited text: 30")).toBeInTheDocument();
    expect(within(tab).getByText("Passage missing")).toBeInTheDocument(); // G3: nothing to open
    fireEvent.click(within(tab).getByRole("button", { name: "Open passage" }));
    const viewer = await within(panel()).findByRole("region", { name: "sop_LC-07.docx" });
    expect(within(viewer).getByRole("listitem", { current: true })).toHaveTextContent("§3.1");
    fireEvent.click(within(tab).getByRole("button", { name: "Add as step from this passage" }));
    const form = await screen.findByRole("form", { name: "Add missing step" });
    expect(within(form).getByRole("list", { name: "Picked passages" })).toHaveTextContent("sop_LC-07.docx · §3.1");
    expect(within(form).getByLabelText("Comes after")).toHaveValue(elementByLabel("Flight scheduled").id);
  });

  it("audit log and map checks", async () => {
    backend();
    renderApp(PATH);
    const audit = await openTab(/Audit log/);
    const row = await within(audit).findByRole("row", { name: /Confirmed step/ });
    expect(row).toHaveTextContent("Draft load plan");
    const checks = await openTab(/Map checks/);
    const mustFix = await within(checks).findByRole("region", { name: "Must fix" });
    expect(mustFix).toHaveTextContent("L4");
    expect(within(checks).getByRole("region", { name: "Worth a look" })).toHaveTextContent("line crossings");
    fireEvent.click(within(mustFix).getByRole("button", { name: "Go to step" }));
    expect(await within(panel()).findByRole("heading", { name: "Deviation in limits?" })).toBeInTheDocument();
  });

  it("merge decisions: side by side, Accept merge · Keep separate, Split once merged", async () => {
    const api = backend();
    renderApp(PATH);
    const tab = await openTab(/Merge decisions/);
    const first = (await within(tab).findByText("Resolve special loads")).closest("li");
    if (!first) throw new Error("no card");
    expect(within(first).getByRole("region", { name: "Resolve or offload" })).toHaveTextContent("“Airline ops resolves it”");
    expect(within(first).getByRole("region", { name: "Offload the item" })).toBeInTheDocument();
    expect(first).toHaveTextContent("similarity 0.72");
    expect(within(first).getByRole("button", { name: "Keep separate" })).toBeInTheDocument();
    fireEvent.click(within(first).getByRole("button", { name: "Accept merge" }));
    await waitFor(() => expect(api.calls.some((c) => c.key === "POST /api/merge-proposals/m1/decision")).toBe(true));
    expect(api.calls.find((c) => c.key === "POST /api/merge-proposals/m1/decision")?.body).toEqual({ decision: "accepted" });
    const second = within(tab).getByText("Load and return LIR").closest("li");
    if (!second) throw new Error("no card");
    expect(within(second).getByRole("button", { name: "Split" })).toBeInTheDocument();
    expect(within(second).queryByRole("button", { name: "Keep separate" })).not.toBeInTheDocument();
  });

  it("offers no changes on a published version", async () => {
    backend("published");
    renderApp(PATH);
    const questions = await openTab(/Validation questions/);
    await within(questions).findByText("Is the plan always drafted by T-120?");
    expect(within(questions).queryByRole("button", { name: "Mark answered" })).not.toBeInTheDocument();
    const merges = await openTab(/Merge decisions/);
    await within(merges).findByText("Resolve special loads");
    expect(within(merges).queryByRole("button", { name: "Accept merge" })).not.toBeInTheDocument();
    const rejected = await openTab(/Rejected claims/);
    await within(rejected).findByText("number not found in cited text: 30");
    expect(within(rejected).queryByRole("button", { name: "Add as step from this passage" })).not.toBeInTheDocument();
  });

  it.each([/RACI matrix/, /Validation questions/, /Rejected claims/, /Audit log/, /Merge decisions/, /Map checks/])(
    "has no serious accessibility problems on the %s tab",
    async (name) => {
      backend();
      renderApp(PATH);
      const tab = await openTab(name);
      await waitFor(() => expect(tab.querySelector(".skeleton")).toBeNull());
      expect(await seriousViolations(document.body)).toEqual([]);
    },
  );
});
