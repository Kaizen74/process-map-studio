import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftState, RefreshCheck, RunRecord } from "../../src/api/types";
import type { Graph } from "../../src/lib/mapTypes";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp, type Handler } from "../renderApp";
import { SAMPLE, layoutFor } from "../sampleMap";

const VID = SAMPLE.graph.version.id;
const PATH = "/engagements/e1/review";

const MADE_WITH: RunRecord = {
  model: "claude-opus-5-5",
  effort: "high",
  verifier: true,
  instructions: { S1_extract_interview: "1" },
  app_version: "1.0.0",
};
const SAME: RefreshCheck = { made_with: MADE_WITH, now: MADE_WITH, changes: [] };

function backend(refusal: string | null = null, check: RefreshCheck | null = SAME) {
  const graph: Graph = structuredClone(SAMPLE.graph);
  graph.elements = graph.elements.map((e, i) => (i === 1 || i === 2 ? { ...e, review_status: "confirmed" } : e));
  const draft: DraftState = {
    job: null,
    version: { id: VID, engagement_id: "e1", label: "v0.1", state: "draft", created_at: "2026-09-27T10:00:00+00:00" },
    summary: { steps: 8, needs_check: 0, verified: 21, rejected: 0, open_questions: 5, scrubbed: 0 },
  };
  const routes: Record<string, Handler> = {
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/draft": () => ({ body: draft }),
    "GET /api/engagements/e1/sources": () => ({ body: [] }),
    [`GET /api/versions/${VID}/graph`]: () => ({ body: graph }),
    [`GET /api/versions/${VID}/layout`]: (_body, url) => ({ body: layoutFor(url) }),
    [`GET /api/versions/${VID}/rejected-claims`]: () => ({
      body: { items: [], total: 0, scrub_count: 0, instruction_like_count: 0 },
    }),
    [`GET /api/versions/${VID}/refresh-check`]: () =>
      check ? { body: check } : { status: 500, body: { error: { code: "IO", message: "Broken", details: {} } } },
    [`POST /api/versions/${VID}/refresh`]: () =>
      refusal
        ? { status: 409, body: { error: { code: "CONFLICT", message: refusal, details: {} } } }
        : { status: 202, body: { job_id: "job-2" } },
  };
  return fakeApi(routes);
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

async function openRefresh() {
  renderApp(PATH);
  fireEvent.click(await screen.findByRole("button", { name: "More" }));
  fireEvent.click(within(screen.getByRole("dialog", { name: "More" })).getByRole("button", { name: "Refresh draft from sources" }));
  return screen.findByRole("dialog", { name: "Refresh draft from sources" });
}

describe("Refresh draft from sources on Review (PRD §3.5, constraint 8)", () => {
  it("says what stays as it is, starts the run and opens the Draft screen", async () => {
    const api = backend();
    const dialog = await openRefresh();
    expect(dialog).toHaveTextContent("The 2 steps you confirmed, edited, added or rejected stay exactly as they are.");
    expect(dialog).toHaveTextContent("The draft v0.1 then gets the next number.");
    expect(
      await within(dialog).findByText("Claude's model, settings and instructions are the same as when this draft was made."),
    ).toBeInTheDocument();
    expect(within(dialog).queryByRole("heading", { name: "Since this draft was made" })).toBeNull();
    expect(await seriousViolations(document.body)).toEqual([]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Refresh draft" }));
    await waitFor(() => expect(api.calls.some((c) => c.key === `POST /api/versions/${VID}/refresh`)).toBe(true));
    expect(await screen.findByRole("heading", { level: 1, name: "Draft" })).toBeInTheDocument();
  });

  it("explains a refusal and stays on Review; Cancel changes nothing", async () => {
    const api = backend("A draft map is already being made.");
    const dialog = await openRefresh();
    fireEvent.click(within(dialog).getByRole("button", { name: "Refresh draft" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("A draft map is already being made.");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog", { name: "Refresh draft from sources" })).toBeNull();
    expect(screen.getByRole("radiogroup", { name: "Lens" })).toBeInTheDocument();
    expect(api.calls.filter((c) => c.key.endsWith("/refresh"))).toHaveLength(1);
  });

  it("warns, without blocking, when the model, verifier or instructions differ from the draft's run", async () => {
    const changes = [
      "The model changed: this draft was made with claude-opus-5-5; a refresh now uses claude-sonnet-5-5.",
      "The independent verifier checked this draft, but it is now switched off in Settings, so fresh suggestions would reach the map without that second check.",
    ];
    const api = backend(null, { made_with: MADE_WITH, now: { ...MADE_WITH, model: "claude-sonnet-5-5", verifier: false }, changes });
    const dialog = await openRefresh();
    const drift = await within(dialog).findByRole("region", { name: "Since this draft was made" });
    const items = within(drift).getAllByRole("listitem").map((li) => li.textContent);
    expect(items).toEqual(changes);
    expect(drift).toHaveTextContent("You can still refresh. To use what made this draft, change Settings first.");
    expect(await seriousViolations(document.body)).toEqual([]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Refresh draft" }));
    await waitFor(() => expect(api.calls.some((c) => c.key === `POST /api/versions/${VID}/refresh`)).toBe(true));
  });

  it("still offers the refresh when the check can't be made", async () => {
    backend(null, null);
    const dialog = await openRefresh();
    expect(
      await within(dialog).findByText("The app couldn't check how this draft was made. You can still refresh."),
    ).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Refresh draft" })).toBeEnabled();
  });
});
