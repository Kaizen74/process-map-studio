import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftState } from "../../src/api/types";
import type { Graph } from "../../src/lib/mapTypes";
import type { NextSteps, QualityCard } from "../../src/lib/reviewTypes";
import { seriousViolations } from "../axe";
import {
  ENGAGEMENT,
  READINESS,
  fakeApi,
  renderApp,
  type Handler,
  type FakeResponse,
} from "../renderApp";
import { SAMPLE, elementByLabel, layoutFor } from "../sampleMap";

const VID = SAMPLE.graph.version.id;
const PATH = "/engagements/e1/review";
const NAMES = ["Provenance green", "Evidence verified", "Diamonds closed", "Lanes and ownership", "Flags executable",
  "Fully reviewed", "Facts, interpretation and recommendation separated", "Anonymised", "Images contained",
  "60-minute validatable"]; // prettier-ignore

const CARD: QualityCard = {
  checks: NAMES.map((name, i) => ({
    id: `Q${i + 1}`,
    name,
    status: i === 5 ? "fail" : "pass",
    hard: i < 9,
    detail: i === 5 ? "8 steps not reviewed yet." : "Fine.",
  })),
  warnings: ['Activity "Issue load sheet" has no time stated.'],
  all_green: false,
};

function backend(publish: FakeResponse, next: NextSteps = SAMPLE.next_steps) {
  const state = "draft" as const;
  const graph: Graph = {
    ...structuredClone(SAMPLE.graph),
    version: { ...SAMPLE.graph.version, state },
  };
  const draft: DraftState = {
    job: null,
    version: {
      id: VID,
      engagement_id: "e1",
      label: "v0.1",
      state,
      created_at: "2026-09-27T10:00:00+00:00",
    },
    summary: {
      steps: 8,
      needs_check: 0,
      verified: 21,
      rejected: 0,
      open_questions: 0,
      scrubbed: 0,
    },
  };
  const routes: Record<string, Handler> = {
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/draft": () => ({ body: draft }),
    [`GET /api/versions/${VID}/graph`]: () => ({ body: graph }),
    [`GET /api/versions/${VID}/layout`]: (_body, url) => ({
      body: layoutFor(url),
    }),
    [`GET /api/versions/${VID}/quality-card`]: () => ({ body: CARD }),
    [`POST /api/versions/${VID}/publish`]: () => publish,
    [`GET /api/versions/${VID}/next-steps`]: () => ({ body: next }),
  };
  for (const [id, element] of Object.entries(SAMPLE.elements))
    routes[`GET /api/elements/${id}`] = () => ({ body: element });
  return fakeApi(routes);
}

const blocked = (element: string): FakeResponse => ({
  status: 409,
  body: {
    error: {
      code: "PUBLISH_BLOCKED",
      message: "This draft can't be published yet: 2 things to fix.",
      details: {
        blockers: [
          {
            type: "lint_failure",
            id: "L9",
            element_id: element,
            message: "Activity “Issue load sheet” has no way out.",
          },
          {
            type: "quality_check",
            id: "Q8",
            element_id: null,
            message: "Anonymised: a name appears in the md export.",
          },
          {
            type: "unreviewed_element",
            id: element,
            element_id: element,
            message: "“Issue load sheet” hasn't been reviewed yet.",
          },
        ],
      },
    },
  },
});

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

const qualityButton = () =>
  screen.findByRole("button", { name: /Quality card: 8 of 9 green/ });

describe("the quality card and Publish (PRD §5.7.1, §5.7.9)", () => {
  it("the banner counts the green hard checks; the popover lists all ten with their details", async () => {
    backend({ body: {} });
    renderApp(PATH);
    fireEvent.click(await qualityButton());
    const popover = screen.getByRole("dialog", { name: "Quality card" });
    const checks = within(popover)
      .getAllByRole("listitem")
      .filter((li) => li.closest('[aria-label="Quality checks"]'));
    expect(checks).toHaveLength(10);
    expect(within(popover).getByText("8 steps not reviewed yet.")).toHaveClass(
      "quality__detail--fail",
    );
    expect(popover).toHaveTextContent(
      'Activity "Issue load sheet" has no time stated.',
    );
    expect(popover).toHaveTextContent("Fully reviewed : Fail");
    expect(await seriousViolations(document.body)).toEqual([]);
    fireEvent.click(within(popover).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog", { name: "Quality card" })).toBeNull();
  });

  it("a refused publish lists what to do, grouped and in order; a row goes to its step", async () => {
    // 2026-10-28 (Eric): grouped by what to do, never by check code, the same as "What to do next".
    const issue = elementByLabel("Issue load sheet").id;
    const next: NextSteps = {
      ready_to_publish: false,
      steps: [
        { key: "fix_map", title: "Fix 2 problems on the map", detail: "These must be fixed before publishing. Each opens its step.", count: 2, bulk: 0,
          items: [{ message: "Activity “Issue load sheet” has no way out.", element_id: issue },
                  { message: "Anonymised: a name appears in the md export.", element_id: null }] }, // prettier-ignore
        { key: "review_steps", title: "Review 1 step", detail: "Fix the problems above first; then confirm, edit or reject these.", count: 1, bulk: 0, items: [] }, // prettier-ignore
      ],
    };
    backend(blocked(issue), next);
    renderApp(PATH);
    await qualityButton();
    fireEvent.click(screen.getByRole("button", { name: "Publish" }));
    const popover = await screen.findByRole("dialog", {
      name: "Publish blocked",
    });
    const list = within(popover).getByRole("list", {
      name: "What to do before publishing",
    });
    expect(
      within(list)
        .getAllByRole("listitem")
        .filter((li) => li.parentElement === list)
        .map((li) => li.querySelector(".next-steps__title")?.textContent),
    ).toEqual(["Fix 2 problems on the map", "Review 1 step"]);
    expect(list).toHaveTextContent(
      "Anonymised: a name appears in the md export.",
    );
    expect(list).not.toHaveTextContent("lint_failure"); // no check codes
    expect(within(list).getAllByRole("button")).toHaveLength(1); // only items about a step are links
    expect(await seriousViolations(document.body)).toEqual([]);
    fireEvent.click(
      within(list).getByRole("button", { name: /Issue load sheet/ }),
    );
    expect(
      screen.queryByRole("dialog", { name: "Publish blocked" }),
    ).toBeNull();
    expect(
      await screen.findByRole("heading", { name: "Issue load sheet" }),
    ).toBeInTheDocument();
  });

  it("a green draft publishes and opens the Published screen", async () => {
    const api = backend({
      body: { id: VID, label: "v1.0", state: "published" },
    });
    renderApp(PATH);
    await qualityButton();
    fireEvent.click(screen.getByRole("button", { name: "Publish" }));
    await waitFor(() =>
      expect(
        api.calls.some((c) => c.key === `POST /api/versions/${VID}/publish`),
      ).toBe(true),
    );
    expect(await screen.findByText(/Published as v1.0/)).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 1, name: "Published" }),
    ).toBeInTheDocument();
  });

  it("says why when publishing fails for another reason", async () => {
    backend({
      status: 409,
      body: {
        error: {
          code: "CONFLICT",
          message: "Only the current draft can be published.",
          details: {},
        },
      },
    });
    renderApp(PATH);
    await qualityButton();
    fireEvent.click(screen.getByRole("button", { name: "Publish" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Only the current draft can be published.",
    );
  });

  it("shortcuts ignore keys pressed inside the popover", async () => {
    const api = backend({ body: {} });
    renderApp(`${PATH}?step=${elementByLabel("Draft load plan").id}`);
    fireEvent.click(await qualityButton());
    const popover = screen.getByRole("dialog", { name: "Quality card" });
    fireEvent.keyDown(within(popover).getByRole("button", { name: "Close" }), {
      key: "c",
    });
    expect(api.calls.some((c) => c.key.endsWith("/confirm"))).toBe(false);
  });
});
