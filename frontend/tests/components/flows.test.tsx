import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Engagement } from "../../src/api/types";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp, type Handler } from "../renderApp";
import { DIAGRAM, SAMPLE, graphFor, layoutFor } from "../sampleMap";

// One engagement maps one flow (2026-10-28, Eric's cargo manual; DECISIONS 81): drafting keeps to
// this flow and lists the claims about other flows under Review → Outside this flow (backend
// output in the fixture); Setup offers an overview of every flow and "Map another flow from
// these sources", which starts the next engagement with the same documents and roles.

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

const VID = SAMPLE.graph.version.id;
const ASIDE = (() => {
  const first = DIAGRAM.outside_flow.items[0];
  if (!first) throw new Error("the diagram fixture sets claims aside");
  return first;
})();

function review(extra: Record<string, Handler> = {}) {
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/draft": () => ({
      body: { job: null, version: { id: VID, engagement_id: "e1", label: "v0.1", state: "draft",
        created_at: "2026-10-28T10:00:00+00:00" }, summary: null }, // prettier-ignore
    }),
    [`GET /api/versions/${VID}/graph`]: (_body, url) => ({ body: graphFor(url) }),
    [`GET /api/versions/${VID}/layout`]: (_body, url) => ({ body: layoutFor(url) }),
    [`GET /api/sources/${ASIDE.source_id}/segments`]: () => ({
      body: { segments: [{ id: ASIDE.segment_id, seq: 6, anchor: "p. 1", page: 1, section: "", speaker_role: null,
        text: "CARGO ACCEPTANCE: A. ACCEPT CARGO • Verify pieces, weight and dimensions", cited: false,
        instruction_like: false, speaker_label: null, corrected: false, question_id: null }],
        total: 1, page: 1, pages: 1, coverage_pct: null }, // prettier-ignore
    }),
    [`GET /api/sources/${ASIDE.source_id}`]: () => ({ body: { id: ASIDE.source_id, kind: "manual", format: "pdf" } }),
    ...extra,
  });
}

const tablist = () => screen.findByRole("tablist", { name: "Review workbench" });

describe("Review: Outside this flow", () => {
  it("lists the claims about another flow, with their passage, and adds a step from one", async () => {
    review({ [`GET /api/versions/${VID}/outside-flow`]: () => ({ body: DIAGRAM.outside_flow }) });
    const { container } = renderApp("/engagements/e1/review");
    fireEvent.click(await within(await tablist()).findByRole("tab", { name: "Outside this flow (2)" }));
    const tab = screen.getByRole("tabpanel");
    expect(within(tab).getByText(/2 claims in your documents describe another flow/)).toBeInTheDocument();
    expect(within(tab).getByText("Cargo acceptance verifies pieces, weight and dimensions.")).toBeInTheDocument();
    expect(within(tab).getByText("The Build-up team secures and nets the ULDs as required.")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
    const [open] = within(tab).getAllByRole("button", { name: "Open passage" });
    if (open) fireEvent.click(open);
    expect(await screen.findByRole("region", { name: "process_flow_diagram.pdf" })).toBeInTheDocument();
    const [add] = within(tab).getAllByRole("button", { name: "Add as step from this passage" });
    if (add) fireEvent.click(add);
    const form = await screen.findByRole("form", { name: "Add missing step" });
    expect(within(form).getByRole("list", { name: "Picked passages" })).toHaveTextContent("process_flow_diagram.pdf · p. 1");
  });

  it("has no tab when every claim belongs to this flow", async () => {
    review();
    renderApp("/engagements/e1/review");
    const tabs = await tablist();
    await within(tabs).findByRole("tab", { name: /Rejected claims/ });
    expect(within(tabs).queryByRole("tab", { name: /Outside this flow/ })).toBeNull();
  });
});

function setup(extra: Record<string, Handler> = {}) {
  let engagement: Engagement = { ...ENGAGEMENT };
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: engagement }),
    "PATCH /api/engagements/e1": (body) => {
      engagement = { ...engagement, ...(body as object) };
      return { body: engagement };
    },
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/roles": () => ({ body: [] }),
    ...extra,
  });
}

const scope = () => screen.getByRole("region", { name: "Process scope" });
const another = () => screen.getByRole("region", { name: "Another flow in these documents" });

describe("Setup: one flow or every flow", () => {
  it("maps one flow unless Eric ticks the overview, and saves the answer", async () => {
    const { calls } = setup();
    renderApp("/engagements/e1/setup");
    await screen.findByLabelText("Engagement name");
    const overview = within(scope()).getByRole("checkbox", { name: "Map every flow in these documents (overview)" });
    expect(overview).not.toBeChecked();
    expect(within(scope()).getByText(/use Map another flow from these sources below/)).toBeInTheDocument();
    fireEvent.click(overview);
    fireEvent.click(within(scope()).getByRole("button", { name: "Save scope" }));
    expect(await screen.findByText("Scope saved.")).toBeInTheDocument();
    const body = calls.find((c) => c.key === "PATCH /api/engagements/e1")?.body as Record<string, unknown>;
    expect(body).toMatchObject({ every_flow: true });
  });

  it("starts another flow with the same documents and opens its Setup", async () => {
    const made: Engagement = { ...ENGAGEMENT, id: "e2", name: "Export", trigger: "Cargo received for export",
      end_point: "ULDs built up", out_of_scope: "Import" }; // prettier-ignore
    const { calls } = setup({
      "POST /api/engagements/e1/another-flow": () => ({ status: 201, body: made }),
      "GET /api/engagements/e2": () => ({ body: made }),
      "GET /api/engagements/e2/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e2/roles": () => ({ body: [] }),
    });
    const { container } = renderApp("/engagements/e1/setup");
    await screen.findByLabelText("Engagement name");
    fireEvent.click(within(another()).getByRole("button", { name: "Map another flow from these sources…" }));
    const dialog = screen.getByRole("dialog", { name: "Map another flow" });
    expect(await seriousViolations(container)).toEqual([]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Start this flow" }));
    expect(await within(dialog).findByText(/Please give the engagement a name/)).toBeInTheDocument();
    expect(calls.some((c) => c.key === "POST /api/engagements/e1/another-flow")).toBe(false);

    fireEvent.change(within(dialog).getByLabelText("Engagement name"), { target: { value: "Export" } });
    fireEvent.change(within(dialog).getByLabelText("Trigger"), { target: { value: "Cargo received for export" } });
    fireEvent.change(within(dialog).getByLabelText("End point"), { target: { value: "ULDs built up" } });
    fireEvent.change(within(dialog).getByLabelText("Out of scope"), { target: { value: "Import" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Start this flow" }));
    expect(
      await screen.findByText(
        "Started Export with the same documents, roles and names to hide. Check its scope, then draft it.",
      ),
    ).toBeInTheDocument();
    const sent = calls.find((c) => c.key === "POST /api/engagements/e1/another-flow");
    expect(sent?.body).toEqual({ name: "Export", trigger: "Cargo received for export", end_point: "ULDs built up",
      out_of_scope: "Import" }); // prettier-ignore
    expect(await screen.findByDisplayValue("Cargo received for export")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Setup" })).toHaveFocus());
    expect(screen.queryByRole("dialog", { name: "Map another flow" })).toBeNull();
  });

  it("says plainly when the next flow couldn't be started", async () => {
    setup({
      "POST /api/engagements/e1/another-flow": () => ({
        status: 404,
        body: { error: { code: "NOT_FOUND", message: "That engagement doesn't exist. It may have been deleted.", details: {} } },
      }),
    });
    renderApp("/engagements/e1/setup");
    await screen.findByLabelText("Engagement name");
    fireEvent.click(within(another()).getByRole("button", { name: "Map another flow from these sources…" }));
    const dialog = screen.getByRole("dialog", { name: "Map another flow" });
    fireEvent.change(within(dialog).getByLabelText("Engagement name"), { target: { value: "Export" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Start this flow" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("That engagement doesn't exist.");
  });
});
