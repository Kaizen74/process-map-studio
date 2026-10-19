import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftState } from "../../src/api/types";
import type { Graph } from "../../src/lib/mapTypes";
import type { VersionDetail, VersionSummary } from "../../src/lib/reviewTypes";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp, type Handler } from "../renderApp";
import { SAMPLE, layoutFor } from "../sampleMap";

const V1 = SAMPLE.graph.version.id;
const V0 = "v-old";
const PATH = "/engagements/e1/published";

const summary = (id: string, label: string, state: string, at: string): VersionSummary => ({
  id,
  engagement_id: "e1",
  label,
  state,
  created_at: at,
  published_at: at,
  published_by: "Eric",
  parent_version_id: null,
});

function backend({ versions, draftExists = false }: { versions: VersionSummary[]; draftExists?: boolean }) {
  const confirmed = (state: string): Graph => ({
    ...structuredClone(SAMPLE.graph),
    version: { ...SAMPLE.graph.version, state },
    elements: SAMPLE.graph.elements.map((e) => ({ ...e, review_status: "confirmed" })),
  });
  const detail = (v: VersionSummary): VersionDetail => ({
    ...v,
    review: { reviewed: 8, total: 8 },
    acceptance: { drafted: 9, confirmed: 6, edited: 2, rejected: 1, unreviewed: 0, added: 2 },
    change_log:
      v.id === V1
        ? [
            { change: "confirmed", step: "Draft load plan", stable_key: "draft-load-plan" },
            { change: "edited", step: "Issue load sheet", stable_key: "issue-load-sheet" },
          ]
        : [],
    quality_card: null,
  });
  const draft: DraftState = { job: null, version: null, summary: null };
  const all = draftExists ? [summary("v-draft", "v1.1 draft", "draft", "2026-09-28T11:00:00+00:00"), ...versions] : versions;
  const routes: Record<string, Handler> = {
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/draft": () => ({ body: draft }),
    "GET /api/engagements/e1/versions": () => ({ body: all }),
    "GET /api/engagements/e1/sources": () => ({ body: [] }),
    [`POST /api/versions/${V1}/reopen`]: () => ({
      status: 201,
      body: detail(summary("v-new", "v1.1 draft", "draft", "2026-09-28T11:00:00+00:00")),
    }),
  };
  for (const v of versions) {
    routes[`GET /api/versions/${v.id}`] = () => ({ body: detail(v) });
    routes[`GET /api/versions/${v.id}/graph`] = () => ({ body: { ...confirmed(v.state), version: { ...confirmed(v.state).version, id: v.id, label: v.label } } });
    routes[`GET /api/versions/${v.id}/layout`] = (_body, url) => ({ body: layoutFor(url) });
    routes[`GET /api/versions/${v.id}/questions`] = () => ({ body: [] });
    routes[`GET /api/versions/${v.id}/rejected-claims`] = () => ({ body: { items: [], total: 0, scrub_count: 0, instruction_like_count: 0 } });
  }
  for (const [id, element] of Object.entries(SAMPLE.elements)) {
    routes[`GET /api/elements/${id}`] = () => ({ body: { ...element, review_status: "confirmed" } });
  }
  return fakeApi(routes);
}

const V1_SUMMARY = summary(V1, "v1.0", "published", "2026-09-28T09:00:00+00:00");

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("the Published screen (PRD §5.4, §5.9)", () => {
  it("says so when nothing is published", async () => {
    backend({ versions: [] });
    renderApp(PATH);
    expect(await screen.findByText("Nothing published yet. Review and publish from the Review screen.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Review" })).toHaveAttribute("href", "/engagements/e1/review");
  });

  it("shows the published version read-only: no review controls, outlines, Merge or Map checks", async () => {
    backend({ versions: [V1_SUMMARY] });
    const { container } = renderApp(PATH);
    expect(await screen.findByText("Published v1.0")).toBeInTheDocument();
    expect(screen.getByText(/Read-only. Validated by Eric on 28 Sep 2026. Reopening creates a new draft version./)).toBeInTheDocument();
    await screen.findByRole("radiogroup", { name: "Lens" });
    expect(container.querySelectorAll(".map-node--unreviewed")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: "More" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Publish" })).toBeNull();
    const tabs = screen.getByRole("tablist", { name: "Review workbench" });
    expect(within(tabs).queryByRole("tab", { name: /Merge decisions/ })).toBeNull();
    expect(within(tabs).queryByRole("tab", { name: /Map checks/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /^Activity, Draft load plan/ }));
    const panel = await screen.findByRole("complementary", { name: "Step details" });
    await within(panel).findByRole("heading", { name: "Draft load plan" });
    expect(within(panel).queryByRole("button", { name: "Confirm as drafted" })).toBeNull();
    expect(within(panel).queryByRole("button", { name: /Edit/ })).toBeNull();
    expect(within(panel).queryByRole("button", { name: "Add a missing step after this one" })).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Table" }));
    expect(await screen.findByRole("table", { name: "Steps in process order" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Edit in place/ })).toBeNull();
    expect(await seriousViolations(document.body)).toEqual([]);
  });

  it("states the version's signal strength in words and bars", async () => {
    const signal = { level: "moderate" as const, label: "Moderate", score: 2, detail: "Interviews with supporting records." };
    backend({ versions: [{ ...V1_SUMMARY, signal }] });
    const { container } = renderApp(PATH);
    expect(await screen.findByText("Published v1.0")).toBeInTheDocument();
    const meter = container.querySelector(".version-banner .signal");
    expect(meter).toHaveTextContent("Signal strength: Moderate (2 of 3)");
    expect(meter).not.toHaveTextContent("Interviews with supporting records.");
    expect(meter?.querySelectorAll(".signal__bar--on")).toHaveLength(2);
  });

  it("lists what changed while it was the draft", async () => {
    backend({ versions: [V1_SUMMARY] });
    renderApp(PATH);
    const log = await screen.findByRole("region", { name: "Changes in this version" });
    await within(log).findByText("Issue load sheet");
    expect(log).toHaveTextContent("ConfirmedDraft load plan");
    expect(log).toHaveTextContent("EditedIssue load sheet");
    // Deep review item 4: how much of Claude's draft was kept, in one plain sentence.
    expect(log).toHaveTextContent(
      "Of the 9 steps Claude drafted, you kept 6 as drafted, edited 2 and rejected 1. You added 2 steps yourself.",
    );
  });

  it("picks earlier versions, labelled superseded; only the latest reopens", async () => {
    backend({ versions: [V1_SUMMARY, summary(V0, "v0.9", "superseded", "2026-09-20T09:00:00+00:00")] });
    renderApp(PATH);
    const picker = await screen.findByLabelText("Version");
    expect(within(picker).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "v1.0 · published 28 Sep 2026",
      "v0.9 · superseded 20 Sep 2026",
    ]);
    fireEvent.change(picker, { target: { value: V0 } });
    expect(await screen.findByText("Superseded v0.9")).toBeInTheDocument();
    expect(screen.getByText(/A later version has been published since./)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reopen as new draft" })).toBeNull();
  });

  it("Reopen as new draft goes to Review; with a draft already open it links there instead", async () => {
    const api = backend({ versions: [V1_SUMMARY] });
    renderApp(PATH);
    fireEvent.click(await screen.findByRole("button", { name: "Reopen as new draft" }));
    await waitFor(() => expect(api.calls.some((c) => c.key === `POST /api/versions/${V1}/reopen`)).toBe(true));
    expect(await screen.findByText(/Reopened as v1.1 draft/)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1, name: "Review" })).toBeInTheDocument();
  });

  it("with a draft already open, links to it instead of reopening", async () => {
    backend({ versions: [V1_SUMMARY], draftExists: true });
    renderApp(PATH);
    expect(await screen.findByRole("link", { name: "Go to the draft (v1.1 draft)" })).toHaveAttribute(
      "href",
      "/engagements/e1/review",
    );
    expect(screen.queryByRole("button", { name: "Reopen as new draft" })).toBeNull();
  });

  it("the review screen points to Published when nothing is left to review", async () => {
    backend({ versions: [V1_SUMMARY] });
    renderApp("/engagements/e1/review");
    expect(await screen.findByText(/Nothing to review: v1.0 is published./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Published" })).toHaveAttribute("href", PATH);
  });
});
