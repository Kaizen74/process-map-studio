import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftState } from "../../src/api/types";
import type { ElementDetail, Graph } from "../../src/lib/mapTypes";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp, type Handler } from "../renderApp";
import { SAMPLE, elementByLabel, layoutFor } from "../sampleMap";

const VID = SAMPLE.graph.version.id;
const PATH = "/engagements/e1/review";
const AFTER: Record<string, string> = { confirm: "confirmed", reject: "rejected", restore: "draft" };

/** A fake backend that remembers review changes and edits, like the real one. */
function backend() {
  const graph: Graph = structuredClone(SAMPLE.graph);
  const elements: Record<string, ElementDetail> = structuredClone(SAMPLE.elements);
  const draft: DraftState = {
    job: null,
    version: { id: VID, engagement_id: "e1", label: "v0.1", state: "draft", created_at: "2026-09-27T10:00:00+00:00" },
    summary: { steps: 8, needs_check: 0, verified: 21, rejected: 0, open_questions: 0, scrubbed: 0 },
  };
  const routes: Record<string, Handler> = {
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/draft": () => ({ body: draft }),
    [`GET /api/versions/${VID}/graph`]: () => ({ body: graph }),
    [`GET /api/versions/${VID}/layout`]: (_body, url) => ({ body: layoutFor(url) }),
  };
  const change = (id: string, patch: Partial<ElementDetail>) => {
    const detail = elements[id];
    if (detail) Object.assign(detail, patch);
    graph.elements = graph.elements.map((e) => (e.id === id ? { ...e, ...(patch as object) } : e));
    return { body: detail };
  };
  for (const id of Object.keys(elements)) {
    routes[`GET /api/elements/${id}`] = () => ({ body: elements[id] });
    for (const action of ["confirm", "reject", "restore"]) {
      routes[`POST /api/elements/${id}/${action}`] = () => change(id, { review_status: AFTER[action] ?? "draft" });
    }
    routes[`PATCH /api/elements/${id}`] = (body) => {
      const b = body as { label?: string; kpi?: string; work_min?: number | null };
      const time = elements[id]?.time;
      const patch: Partial<ElementDetail> = { review_status: "edited" };
      if (b.label !== undefined) patch.label = b.label;
      if (b.kpi !== undefined) patch.kpi = b.kpi;
      if (b.work_min !== undefined && time) patch.time = { ...time, work_min: b.work_min };
      return change(id, patch);
    };
  }
  return fakeApi(routes);
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

const panel = () => screen.getByRole("complementary");
const key = (k: string, target: Element | Document = document.body) => fireEvent.keyDown(target, { key: k });

describe("the table view (PRD §5.7.4)", () => {
  it("switches from the map, filters, and selects a step from its row", async () => {
    backend();
    renderApp(PATH);
    fireEvent.click(await screen.findByRole("radio", { name: "Table" }));
    const table = await screen.findByRole("table", { name: "Steps in process order" });
    expect(within(table).getAllByRole("row")).toHaveLength(11); // header + 10 steps (v1.10 A.5)
    expect(screen.queryByRole("radiogroup", { name: "Lens" })).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: /Contested/ }));
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.every((r) => r.textContent?.includes("Contested"))).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: /All steps/ }));
    fireEvent.click(within(table).getByRole("button", { name: "Draft load plan" }));
    expect(await within(panel()).findByRole("heading", { name: "Draft load plan" })).toBeInTheDocument();
  });

  it("remembers the table in the address, so a reload keeps it", async () => {
    backend();
    renderApp(`${PATH}?view=table`);
    expect(await screen.findByRole("table", { name: "Steps in process order" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Map" }));
    expect(await screen.findByRole("radiogroup", { name: "Lens" })).toBeInTheDocument();
  });

  it("edits a step in place with the shared rules, then moves on", async () => {
    const api = backend();
    renderApp(`${PATH}?view=table`);
    const table = await screen.findByRole("table", { name: "Steps in process order" });
    fireEvent.click(within(table).getByRole("button", { name: "Edit in place: Draft load plan" }));
    const form = screen.getByRole("form", { name: "Edit Draft load plan in place" });
    fireEvent.change(within(form).getByLabelText("Work (minutes)"), { target: { value: "-3" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save" }));
    expect(within(form).getByLabelText("Work (minutes)")).toHaveAccessibleDescription("Minutes must be between 0 and 10,000.");
    fireEvent.change(within(form).getByLabelText("Work (minutes)"), { target: { value: "25" } });
    fireEvent.change(within(form).getByLabelText("KPI"), { target: { value: "Plan issued by T-90" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.calls.some((c) => c.key.startsWith("PATCH"))).toBe(true));
    expect(api.calls.find((c) => c.key.startsWith("PATCH"))?.body).toEqual({ work_min: 25, kpi: "Plan issued by T-90" });
    expect(await within(panel()).findByRole("heading", { name: "Approve load plan" })).toBeInTheDocument();
    const row = within(table).getByRole("button", { name: "Draft load plan" }).closest("tr");
    await waitFor(() => expect(row).toHaveTextContent("~25 min"));
    expect(row).toHaveTextContent("Edited");
  });

  it("a contested Accountable is left to the full edit form; Esc discards", async () => {
    backend();
    renderApp(`${PATH}?view=table`);
    const table = await screen.findByRole("table", { name: "Steps in process order" });
    fireEvent.click(within(table).getByRole("button", { name: "Edit in place: Deviation in limits?" }));
    const form = screen.getByRole("form", { name: "Edit Deviation in limits? in place" });
    expect(within(form).getByText(/several roles \(contested\)/)).toBeInTheDocument();
    key("Escape", within(form).getByLabelText("KPI")); // typing: stays open
    expect(screen.getByRole("form", { name: /in place/ })).toBeInTheDocument();
    key("Escape");
    expect(screen.queryByRole("form", { name: /in place/ })).toBeNull();
  });

  it("has no serious accessibility problems, with the in-place editor open", async () => {
    backend();
    renderApp(`${PATH}?view=table`);
    const table = await screen.findByRole("table", { name: "Steps in process order" });
    fireEvent.click(within(table).getByRole("button", { name: "Edit in place: Draft load plan" }));
    expect(await seriousViolations(document.body)).toEqual([]);
  });
});

describe("the keyboard (PRD §5.8)", () => {
  it("J and K move along the process; C confirms and moves on; R rejects", async () => {
    const api = backend();
    renderApp(PATH);
    await screen.findByRole("radiogroup", { name: "Lens" });
    key("j");
    expect(await within(panel()).findByText(/Where the process starts/)).toBeInTheDocument();
    key("j");
    expect(await within(panel()).findByRole("heading", { name: "Draft load plan" })).toBeInTheDocument();
    key("k");
    expect(await within(panel()).findByText(/Where the process starts/)).toBeInTheDocument();
    key("j");
    await within(panel()).findByRole("heading", { name: "Draft load plan" });
    key("c");
    await waitFor(() => expect(api.calls.some((c) => c.key === `POST /api/elements/${elementByLabel("Draft load plan").id}/confirm`)).toBe(true));
    expect(await within(panel()).findByRole("heading", { name: "Approve load plan" })).toBeInTheDocument();
    key("r");
    await waitFor(() => expect(api.calls.some((c) => c.key === `POST /api/elements/${elementByLabel("Approve load plan").id}/reject`)).toBe(true));
  });

  it("E opens the edit form, where letters type instead of acting", async () => {
    const api = backend();
    renderApp(`${PATH}?step=${elementByLabel("Draft load plan").id}`);
    await within(await screen.findByRole("complementary")).findByRole("button", { name: "Confirm as drafted" });
    key("e");
    const form = await screen.findByRole("form", { name: "Edit step" });
    key("c", within(form).getByLabelText("Name"));
    key("j"); // a form is open: J does not move away
    expect(screen.getByRole("form", { name: "Edit step" })).toBeInTheDocument();
    expect(api.calls.some((c) => c.key.endsWith("/confirm"))).toBe(false);
  });

  it("1–4 switch lens, and ? lists the shortcuts", async () => {
    backend();
    renderApp(PATH);
    await screen.findByRole("radiogroup", { name: "Lens" });
    key("3");
    expect(screen.getByRole("radio", { name: "Confidence" })).toBeChecked();
    key("1");
    expect(screen.getByRole("radio", { name: "Plain" })).toBeChecked();
    key("?");
    const dialog = await screen.findByRole("dialog", { name: "Keyboard shortcuts" });
    expect(dialog).toHaveTextContent("Confirm the selected step as drafted");
    key("j"); // the list is open: nothing moves
    expect(within(screen.getByRole("complementary")).getByRole("heading", { name: "How to review" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog", { name: "Keyboard shortcuts" })).toBeNull();
  });

  it("Esc closes the source viewer, but not while typing", async () => {
    backend();
    renderApp(`${PATH}?step=${elementByLabel("Draft load plan").id}`);
    const evidence = await within(await screen.findByRole("complementary")).findAllByRole("button", { name: /Open .* at/ });
    fireEvent.click(evidence[0] as HTMLElement);
    await screen.findByRole("complementary", { name: "Source" });
    const field = document.body.appendChild(document.createElement("input"));
    key("Escape", field); // typing somewhere on the page: the viewer stays
    expect(screen.getByRole("complementary", { name: "Source" })).toBeInTheDocument();
    field.remove();
    key("Escape");
    expect(await screen.findByRole("complementary", { name: "Step details" })).toBeInTheDocument();
  });
});
