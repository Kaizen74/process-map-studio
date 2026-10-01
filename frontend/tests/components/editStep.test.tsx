import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftState } from "../../src/api/types";
import type { ElementDetail, Graph } from "../../src/lib/mapTypes";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp, type Handler } from "../renderApp";
import { SAMPLE, elementByLabel, layoutFor } from "../sampleMap";

const VID = SAMPLE.graph.version.id;
const PATH = "/engagements/e1/review";
const PLAN = elementByLabel("Draft load plan").id;

type Refusal = { status: number; message: string; field?: string };

/** A fake backend that applies edits like the real one, or refuses them. */
function editingBackend(refusal: Refusal | null = null) {
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
    [`GET /api/versions/${VID}/layout`]: (_body, url) => ({ body: layoutFor(url) }),
  };
  for (const id of Object.keys(elements)) {
    routes[`GET /api/elements/${id}`] = () => ({ body: elements[id] });
    routes[`PATCH /api/elements/${id}`] = (body) => {
      if (refusal) {
        const details = refusal.field ? { field: refusal.field } : {};
        return { status: refusal.status, body: { error: { code: "REFUSED", message: refusal.message, details } } };
      }
      const patch = body as { label?: string; kpi?: string };
      const detail = elements[id];
      if (detail) Object.assign(detail, patch, { review_status: "edited" });
      graph.elements = graph.elements.map((e) => (e.id === id ? { ...e, ...patch, review_status: "edited" } : e));
      return { body: detail };
    };
  }
  return fakeApi(routes);
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

const panel = () => screen.getByRole("complementary", { name: /Edit step|Step details|How to review/ });

async function openEdit() {
  renderApp(`${PATH}?step=${PLAN}`);
  fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
  return screen.findByRole("form", { name: "Edit step" });
}

describe("editing a step (PRD §5.7.6)", () => {
  it("opens with the step's values and saves only what changed, then moves on", async () => {
    const api = editingBackend();
    const form = await openEdit();
    const name = within(form).getByLabelText("Name");
    expect(name).toHaveValue("Draft load plan");
    expect(within(form).getByLabelText("Work (minutes)")).toHaveValue("20");
    fireEvent.change(name, { target: { value: "Build the load plan" } });
    fireEvent.change(within(form).getByLabelText("KPI"), { target: { value: "Plan issued by T-90" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save edits" }));
    await waitFor(() => expect(api.calls.some((c) => c.key === `PATCH /api/elements/${PLAN}`)).toBe(true));
    const call = api.calls.find((c) => c.key === `PATCH /api/elements/${PLAN}`);
    expect(call?.body).toEqual({ label: "Build the load plan", kpi: "Plan issued by T-90" });
    // Auto-advance after Save: the next unreviewed step in process order.
    expect(await within(panel()).findByRole("heading", { name: "Approve load plan" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/steps reviewed/)).toHaveTextContent("1 of 10 steps reviewed"));
  });

  it("refuses to save until the fields pass, with the message under the field", async () => {
    const api = editingBackend();
    const form = await openEdit();
    const name = within(form).getByLabelText("Name");
    fireEvent.change(name, { target: { value: "  " } });
    fireEvent.click(within(form).getByLabelText("Load controller", { selector: "fieldset:first-of-type input" }));
    fireEvent.click(within(form).getByRole("button", { name: "Save edits" }));
    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(name).toHaveAccessibleDescription("Please give the step a name of up to 120 characters.");
    expect(within(form).getByText("Choose who is Accountable for this step.")).toBeInTheDocument();
    expect(within(form).getByText(/2 fields need attention/)).toBeInTheDocument();
    expect(api.calls.some((c) => c.key.startsWith("PATCH"))).toBe(false);
    fireEvent.change(name, { target: { value: "Draft the plan" } }); // messages follow corrections
    expect(name).not.toHaveAttribute("aria-invalid");
    expect(within(form).getByText(/One field needs attention/)).toBeInTheDocument();
  });

  it("shows the server's message under the field it names", async () => {
    editingBackend({
      status: 422,
      field: "kpi",
      message: "The KPI contains a name from your list of names to hide. Use the role instead.",
    });
    const form = await openEdit();
    const kpi = within(form).getByLabelText("KPI");
    fireEvent.change(kpi, { target: { value: "Signed by the lead" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save edits" }));
    await waitFor(() =>
      expect(kpi).toHaveAccessibleDescription(
        "The KPI contains a name from your list of names to hide. Use the role instead.",
      ),
    );
    expect(screen.getByRole("form", { name: "Edit step" })).toBeInTheDocument(); // still open
  });

  it("says why when the whole edit is refused", async () => {
    editingBackend({ status: 409, message: "This version is published and can't be changed. Reopen it as a new draft." });
    const form = await openEdit();
    fireEvent.change(within(form).getByLabelText("KPI"), { target: { value: "Plan issued" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save edits" }));
    expect(await within(form).findByText("This version is published and can't be changed. Reopen it as a new draft.")).toBeInTheDocument();
  });

  it("Cancel and Esc discard; Esc while typing in a field does not", async () => {
    const api = editingBackend();
    const form = await openEdit();
    const name = within(form).getByLabelText("Name");
    fireEvent.change(name, { target: { value: "Changed" } });
    fireEvent.keyDown(name, { key: "Escape" });
    expect(screen.getByRole("form", { name: "Edit step" })).toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(screen.queryByRole("form", { name: "Edit step" })).not.toBeInTheDocument();
    expect(within(panel()).getByRole("heading", { name: "Draft load plan" })).toBeInTheDocument();
    fireEvent.click(within(panel()).getByRole("button", { name: "Edit" }));
    const again = await screen.findByRole("form", { name: "Edit step" });
    expect(within(again).getByLabelText("Name")).toHaveValue("Draft load plan"); // the change was discarded
    fireEvent.click(within(again).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("form", { name: "Edit step" })).not.toBeInTheDocument();
    expect(api.calls.some((c) => c.key.startsWith("PATCH"))).toBe(false);
  });

  it("Save with nothing changed sends nothing", async () => {
    const api = editingBackend();
    const form = await openEdit();
    fireEvent.click(within(form).getByRole("button", { name: "Save edits" }));
    expect(await within(panel()).findByRole("heading", { name: "Approve load plan" })).toBeInTheDocument();
    expect(api.calls.some((c) => c.key.startsWith("PATCH"))).toBe(false);
  });

  it("has no serious accessibility problems with the edit form open", async () => {
    editingBackend();
    await openEdit();
    const form = screen.getByRole("form", { name: "Edit step" });
    fireEvent.click(within(form).getByRole("button", { name: "Save edits" }));
    expect(await seriousViolations(document.body)).toEqual([]);
  });
});
