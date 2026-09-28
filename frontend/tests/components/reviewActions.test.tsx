import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftState } from "../../src/api/types";
import type { ElementDetail, Graph } from "../../src/lib/mapTypes";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp, type Handler } from "../renderApp";
import { SAMPLE, elementByLabel } from "../sampleMap";

const VID = SAMPLE.graph.version.id;
const PATH = "/engagements/e1/review";
const AFTER: Record<string, string> = { confirm: "confirmed", reject: "rejected", restore: "draft" };

/** A fake backend that remembers review changes, like the real one. */
function statefulBackend(refuse: string | null = null) {
  const graph: Graph = structuredClone(SAMPLE.graph);
  const elements: Record<string, ElementDetail> = structuredClone(SAMPLE.elements);
  const draft: DraftState = {
    job: null,
    version: { id: VID, engagement_id: "e1", label: "v0.1", state: "draft", created_at: "2026-09-27T10:00:00+00:00" },
    summary: { steps: 8, needs_check: 0, verified: 21, rejected: 0, open_questions: 5, scrubbed: 0 },
  };
  const routes: Record<string, Handler> = {
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/draft": () => ({ body: draft }),
    [`GET /api/versions/${VID}/graph`]: () => ({ body: graph }),
    [`GET /api/versions/${VID}/layout`]: () => ({ body: SAMPLE.layout }),
  };
  for (const [id] of Object.entries(elements)) {
    routes[`GET /api/elements/${id}`] = () => ({ body: elements[id] });
    for (const action of ["confirm", "reject", "restore"]) {
      routes[`POST /api/elements/${id}/${action}`] = () => {
        if (refuse === action) {
          return { status: 409, body: { error: { code: "CONFLICT", message: "This version is published and can't be changed.", details: {} } } };
        }
        const status = AFTER[action] ?? "draft";
        const detail = elements[id];
        if (detail) detail.review_status = status;
        graph.elements = graph.elements.map((e) => (e.id === id ? { ...e, review_status: status } : e));
        return { body: detail };
      };
    }
  }
  return { api: fakeApi(routes), graph };
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

const panel = () => screen.getByRole("complementary", { name: /Step details|How to review/ });

describe("reviewing steps on the map (PRD §5.7.5, §5.8)", () => {
  it("confirming locks the step and moves on to the next unreviewed one", async () => {
    const { api } = statefulBackend();
    renderApp(`${PATH}?step=${elementByLabel("Draft load plan").id}`);
    fireEvent.click(await screen.findByRole("button", { name: "Confirm as drafted" }));
    const confirmUrl = `POST /api/elements/${elementByLabel("Draft load plan").id}/confirm`;
    await waitFor(() => expect(api.calls.some((c) => c.key === confirmUrl)).toBe(true));
    expect(await within(panel()).findByRole("heading", { name: "Approve load plan" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/steps reviewed/)).toHaveTextContent("1 of 8 steps reviewed"));
    fireEvent.click(screen.getByRole("button", { name: /^Activity, Draft load plan/ }));
    expect(await within(panel()).findByText("Confirmed · locked against AI re-runs")).toBeInTheDocument();
  });

  it("rejecting fades the step; Restore brings it back to unreviewed", async () => {
    statefulBackend();
    const { container } = renderApp(`${PATH}?step=${elementByLabel("Issue load sheet").id}`);
    fireEvent.click(await screen.findByRole("button", { name: "Reject step" }));
    const issue = elementByLabel("Issue load sheet").id;
    await waitFor(() => expect(container.querySelector(`[data-node="${issue}"]`)).toHaveClass("map-node--rejected"));
    fireEvent.click(screen.getByRole("button", { name: /^Activity, Issue load sheet/ }));
    fireEvent.click(await within(panel()).findByRole("button", { name: "Restore" }));
    expect(await within(panel()).findByRole("button", { name: "Confirm as drafted" })).toBeInTheDocument();
    expect(within(panel()).getByRole("heading", { name: "Issue load sheet" })).toBeInTheDocument(); // stays
  });

  it("a refused change rolls back and says why", async () => {
    statefulBackend("confirm");
    const { container } = renderApp(`${PATH}?step=${elementByLabel("Draft load plan").id}`);
    fireEvent.click(await screen.findByRole("button", { name: "Confirm as drafted" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This version is published and can't be changed.");
    expect(await within(panel()).findByRole("heading", { name: "Draft load plan" })).toBeInTheDocument();
    const plan = container.querySelector(`[data-node="${elementByLabel("Draft load plan").id}"]`);
    expect(plan).toHaveClass("map-node--unreviewed");
    expect(screen.getByText(/steps reviewed/)).toHaveTextContent("0 of 8 steps reviewed");
  });

  it("says when every step is reviewed", async () => {
    const { graph } = statefulBackend();
    graph.elements = graph.elements.map((e) =>
      e.label === "Issue load sheet" ? e : { ...e, review_status: "confirmed" },
    );
    renderApp(`${PATH}?step=${elementByLabel("Issue load sheet").id}`);
    fireEvent.click(await screen.findByRole("button", { name: "Confirm as drafted" }));
    expect(await screen.findByText("All steps reviewed")).toBeInTheDocument();
  });

  it("has no serious accessibility problems with the review actions showing", async () => {
    statefulBackend();
    const { container } = renderApp(`${PATH}?step=${elementByLabel("Draft load plan").id}`);
    await screen.findByRole("button", { name: "Confirm as drafted" });
    expect(await seriousViolations(container)).toEqual([]);
  });
});
