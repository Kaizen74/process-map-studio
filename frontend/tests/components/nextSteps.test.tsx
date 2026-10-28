import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { NextSteps } from "../../src/lib/reviewTypes";
import { seriousViolations } from "../axe";
import {
  ENGAGEMENT,
  READINESS,
  fakeApi,
  renderApp,
  type Handler,
} from "../renderApp";
import { DOCUMENTS_ONLY, SAMPLE, graphFor, layoutFor } from "../sampleMap";

// Review → "What to do next" (2026-10-28, Eric: "not sure what I need to do when"): at most three
// things in order, each with one button, from GET /versions/{vid}/next-steps (backend output in
// the fixtures); "Accept remaining" and "Discard all" in one go; the draft map to download.

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

const PATH = "/engagements/e1/review";

function backend(
  map: { graph: typeof SAMPLE.graph; next: NextSteps },
  extra: Record<string, Handler> = {},
) {
  const vid = map.graph.version.id;
  const routes: Record<string, Handler> = {
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/draft": () => ({
      body: { job: null, version: { id: vid, engagement_id: "e1", label: "v0.1", state: map.graph.version.state,
        created_at: "2026-10-28T10:00:00+00:00" }, summary: null }, // prettier-ignore
    }),
    [`GET /api/versions/${vid}/graph`]: (_body, url) => ({
      body: map.graph === SAMPLE.graph ? graphFor(url) : map.graph,
    }),
    [`GET /api/versions/${vid}/layout`]: (_body, url) =>
      map.graph === SAMPLE.graph
        ? { body: layoutFor(url) }
        : { body: DOCUMENTS_ONLY.views.documented },
    [`GET /api/versions/${vid}/next-steps`]: () => ({ body: map.next }),
    ...Object.fromEntries(
      Object.entries(SAMPLE.elements).map(([id, e]) => [
        `GET /api/elements/${id}`,
        () => ({ body: e }),
      ]),
    ),
    ...extra,
  };
  return fakeApi(routes);
}

const card = () => screen.findByRole("region", { name: "What to do next" });

describe("What to do next on a draft", () => {
  it("names the one thing left on a fresh draft, with its buttons and the draft map to download", async () => {
    backend({ graph: SAMPLE.graph, next: SAMPLE.next_steps });
    const { container } = renderApp(PATH);
    const region = await card();
    expect(
      await within(region).findByText("Review 10 steps"),
    ).toBeInTheDocument();
    expect(
      within(region).getByText(
        /accept the 10 that need nothing fixed as drafted/,
      ),
    ).toBeInTheDocument();
    expect(
      within(region).getByRole("button", { name: "Review the next step" }),
    ).toBeInTheDocument();
    expect(
      within(region).getByRole("button", {
        name: "Accept 10 steps as drafted…",
      }),
    ).toBeInTheDocument();
    const download = within(region).getByRole("link", {
      name: "Download draft map",
    });
    expect(download).toHaveAttribute(
      "href",
      `/api/versions/${SAMPLE.graph.version.id}/export/html`,
    );
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("accepts the rest of one phase after asking, and says what it did", async () => {
    const vid = SAMPLE.graph.version.id;
    const plan = SAMPLE.graph.phases.find((p) => p.name === "Plan");
    const { calls } = backend(
      { graph: SAMPLE.graph, next: SAMPLE.next_steps },
      {
        [`POST /api/versions/${vid}/accept-remaining`]: () => ({
          body: { accepted: 2, skipped: [] },
        }),
      },
    );
    renderApp(PATH);
    fireEvent.click(
      await within(await card()).findByRole("button", {
        name: "Accept 10 steps as drafted…",
      }),
    );
    const dialog = screen.getByRole("dialog", {
      name: "Accept steps as drafted?",
    });
    expect(
      within(dialog).getByRole("radio", {
        name: "The whole map (10 steps waiting)",
      }),
    ).toBeChecked();
    fireEvent.click(
      within(dialog).getByRole("radio", { name: /^Plan \(2 steps waiting\)/ }),
    );
    fireEvent.click(within(dialog).getByRole("button", { name: "Accept" }));
    expect(
      await screen.findByText("Accepted 2 steps as drafted."),
    ).toBeInTheDocument();
    const sent = calls.find(
      (c) => c.key === `POST /api/versions/${vid}/accept-remaining`,
    );
    expect(sent?.body).toEqual({ phase_id: plan?.id });
    expect(
      screen.queryByRole("dialog", { name: "Accept steps as drafted?" }),
    ).toBeNull();
  });

  it("puts the must-fix problems first, each a button to its step; skipped steps are named", async () => {
    const graph = { ...DOCUMENTS_ONLY.graph };
    const vid = graph.version.id;
    backend(
      { graph, next: DOCUMENTS_ONLY.next_steps },
      {
        [`POST /api/versions/${vid}/accept-remaining`]: () => ({
          body: { accepted: 4, skipped: [{ element_id: "x", label: "Special loads OK?", reason: "Fix the map problem first: …" },
                                         { element_id: "y", label: "Deviation in limits?", reason: "Fix the map problem first: …" }] }, // prettier-ignore
        }),
      },
    );
    renderApp(PATH);
    const region = await card();
    const steps = await within(region).findAllByText(
      /^(Fix 2 problems on the map|Review 6 steps)$/,
    );
    expect(steps.map((s) => s.textContent)).toEqual([
      "Fix 2 problems on the map",
      "Review 6 steps",
    ]);
    expect(
      within(region).getByRole("button", {
        name: /Special loads OK\?.{0,2} needs at least two labelled exits/,
      }),
    ).toBeInTheDocument();
    fireEvent.click(
      within(region).getByRole("button", {
        name: "Accept 4 steps as drafted…",
      }),
    );
    fireEvent.click(
      within(
        screen.getByRole("dialog", { name: "Accept steps as drafted?" }),
      ).getByRole("button", { name: "Accept" }),
    );
    expect(
      await screen.findByText(
        "Accepted 4 steps as drafted. 2 steps still need you: Special loads OK?, Deviation in limits?.",
      ),
    ).toBeInTheDocument();
  });

  it("discards every suggested picture in one go after asking", async () => {
    const vid = SAMPLE.graph.version.id;
    const next: NextSteps = {
      ready_to_publish: false,
      steps: [
        ...SAMPLE.next_steps.steps,
        { key: "pictures", title: "Keep or discard 7 suggested pictures", detail: "Pictures found in your PDFs. Discard them all if none helps.", count: 7, bulk: 7, items: [] }, // prettier-ignore
      ],
    };
    const { calls } = backend(
      { graph: SAMPLE.graph, next },
      {
        [`POST /api/versions/${vid}/images/discard-suggestions`]: () => ({
          body: { discarded: 7 },
        }),
      },
    );
    renderApp(PATH);
    fireEvent.click(
      await within(await card()).findByRole("button", {
        name: "Discard all 7 suggested…",
      }),
    );
    const dialog = screen.getByRole("dialog", {
      name: "Discard 7 suggested pictures?",
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Discard all" }),
    );
    expect(
      await screen.findByText("Discarded 7 suggested pictures."),
    ).toBeInTheDocument();
    expect(
      calls.some(
        (c) => c.key === `POST /api/versions/${vid}/images/discard-suggestions`,
      ),
    ).toBe(true);
  });

  it("says to publish when nothing is left", async () => {
    backend({ graph: SAMPLE.graph, next: { ready_to_publish: true, steps: [{ key: "publish", title: "Publish the map", detail: "Every check is green.", count: 0, bulk: 0, items: [] }] } }); // prettier-ignore
    renderApp(PATH);
    const region = await card();
    expect(
      await within(region).findByText("Publish the map"),
    ).toBeInTheDocument();
    expect(
      within(region).getByText("Use Publish at the top of the screen."),
    ).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("shows at most three things and counts the rest", async () => {
    const step = (key: NextSteps["steps"][number]["key"], title: string) => ({
      key,
      title,
      detail: "",
      count: 1,
      bulk: 0,
      items: [],
    });
    backend({
      graph: SAMPLE.graph,
      next: {
        ready_to_publish: false,
        steps: [
          step("fix_map", "A"),
          step("check_steps", "B"),
          step("merges", "C"),
          step("review_steps", "D"),
        ],
      },
    });
    renderApp(PATH);
    const region = await card();
    await waitFor(() =>
      expect(within(region).getByText("C")).toBeInTheDocument(),
    );
    expect(within(region).queryByText("D")).toBeNull();
    expect(
      within(region).getByText("Then 1 more thing before publishing."),
    ).toBeInTheDocument();
  });
});
