import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftState, Source } from "../../src/api/types";
import type { ElementDetail, Graph } from "../../src/lib/mapTypes";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp, type Handler } from "../renderApp";
import { SAMPLE, elementByLabel } from "../sampleMap";

const VID = SAMPLE.graph.version.id;
const PATH = "/engagements/e1/review";
const PLAN = elementByLabel("Draft load plan");
const INTERVIEW = "id-13";

function source(id: string, filename: string, kind: string, segments: number, status = "ready"): Source {
  return {
    id,
    engagement_id: "e1",
    kind,
    filename,
    format: "txt",
    mime: "text/plain",
    version_date: "",
    owner: "",
    controlled_copy: false,
    text_status: status,
    error: "",
    segment_count: segments,
    ocr_pages: [],
    suggested_images: 0,
    created_at: "2026-09-27T10:00:00+00:00",
  };
}

const SOURCES = [
  source(INTERVIEW, "interview_transcript.txt", "interview_transcript", 9),
  source("id-15", "sop_LC-07.docx", "sop", 10),
  source("id-99", "still_reading.pdf", "manual", 0, "pending"),
];

type Refusal = { status: number; message: string; field?: string };

/** A fake backend that adds the step after the chosen one, like the real one, or refuses. */
function addingBackend(refusal: Refusal | null = null) {
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
    "GET /api/engagements/e1/sources": () => ({ body: SOURCES }),
    [`GET /api/versions/${VID}/graph`]: () => ({ body: graph }),
    [`GET /api/versions/${VID}/layout`]: () => ({ body: SAMPLE.layout }),
    [`POST /api/versions/${VID}/elements`]: (body) => {
      if (refusal) {
        const details = refusal.field ? { field: refusal.field } : {};
        return { status: refusal.status, body: { error: { code: "REFUSED", message: refusal.message, details } } };
      }
      const b = body as { label: string; kind: "activity"; lane_role_id: string; after_element_id: string; provenance: "O" | "R" };
      const base = elements[PLAN.id];
      if (!base) throw new Error("sample");
      const added: ElementDetail = {
        ...base,
        id: "new-step",
        label: b.label,
        kind: b.kind,
        lane_role_id: b.lane_role_id,
        provenance: b.provenance,
        review_status: "added",
      };
      elements["new-step"] = added;
      routes["GET /api/elements/new-step"] = () => ({ body: added });
      const at = graph.elements.findIndex((e) => e.id === b.after_element_id);
      const summary = { ...PLAN, id: "new-step", label: b.label, review_status: "added", provenance: b.provenance };
      graph.elements = [...graph.elements.slice(0, at + 1), summary, ...graph.elements.slice(at + 1)];
      return { status: 201, body: added };
    },
  };
  for (const id of Object.keys(elements)) routes[`GET /api/elements/${id}`] = () => ({ body: elements[id] });
  for (const s of SOURCES) routes[`GET /api/sources/${s.id}`] = () => ({ body: s });
  for (const [id, page] of Object.entries(SAMPLE.segments)) {
    routes[`GET /api/sources/${id}/segments`] = () => ({ body: page });
  }
  return fakeApi(routes);
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

const panel = () => screen.getByRole("complementary");
const posted = (api: ReturnType<typeof fakeApi>) => api.calls.filter((c) => c.key === `POST /api/versions/${VID}/elements`);

async function openAdd() {
  renderApp(`${PATH}?step=${PLAN.id}`);
  fireEvent.click(await screen.findByRole("button", { name: "Add a missing step after this one" }));
  return screen.findByRole("form", { name: "Add missing step" });
}

describe("adding a missing step (PRD §5.7.6)", () => {
  it("starts after the selected step, in its lane, and needs a passage when observed", async () => {
    const api = addingBackend();
    const form = await openAdd();
    expect(within(form).getByLabelText("Comes after")).toHaveValue(PLAN.id);
    expect(within(form).getByLabelText("Lane")).toHaveValue(PLAN.lane_role_id);
    expect(within(form).getByRole("radio", { name: "Observed in a source" })).toBeChecked();
    fireEvent.click(within(form).getByRole("button", { name: "Add step" }));
    expect(within(form).getByLabelText("Name")).toHaveAccessibleDescription(
      "Please give the step a name of up to 120 characters.",
    );
    expect(within(form).getByText("Pick the passage this step comes from.")).toBeInTheDocument();
    expect(posted(api)).toEqual([]);
  });

  it("picks a passage in a source and adds the step, which is then selected", async () => {
    const api = addingBackend();
    const form = await openAdd();
    fireEvent.change(within(form).getByLabelText("Name"), { target: { value: "Check fuel figures" } });
    fireEvent.click(within(form).getByRole("button", { name: "Pick a passage" }));
    const sources = await within(panel()).findByRole("list", { name: "Sources" });
    expect(within(sources).queryByText("still_reading.pdf")).not.toBeInTheDocument(); // not readable yet
    fireEvent.click(within(sources).getByRole("button", { name: /interview_transcript\.txt/ }));
    fireEvent.click(await within(panel()).findByRole("button", { name: "Use this passage, 06:40" }));
    const back = await screen.findByRole("form", { name: "Add missing step" });
    const picked = within(back).getByRole("list", { name: "Picked passages" });
    expect(picked).toHaveTextContent("interview_transcript.txt · 06:40");
    expect(within(back).getByLabelText("Name")).toHaveValue("Check fuel figures"); // kept
    fireEvent.click(within(back).getByRole("button", { name: "Add step" }));
    await waitFor(() => expect(posted(api)).toHaveLength(1));
    expect(posted(api)[0]?.body).toEqual({
      kind: "activity",
      label: "Check fuel figures",
      lane_role_id: PLAN.lane_role_id,
      after_element_id: PLAN.id,
      provenance: "O",
      segment_ids: ["id-12"],
      r_reference: "",
      mechanism: "judgment",
    });
    expect(await within(panel()).findByRole("heading", { name: "Check fuel figures" })).toBeInTheDocument();
    expect(screen.getByText(/steps reviewed/)).toHaveTextContent("1 of 11 steps reviewed");
  });

  it("a recommended step needs a reference instead of a passage", async () => {
    const api = addingBackend();
    const form = await openAdd();
    fireEvent.change(within(form).getByLabelText("Name"), { target: { value: "Cross-check the load sheet" } });
    fireEvent.change(within(form).getByLabelText("Kind"), { target: { value: "decision" } });
    fireEvent.click(within(form).getByRole("radio", { name: "Recommended practice" }));
    fireEvent.click(within(form).getByRole("button", { name: "Add step" }));
    expect(within(form).getByLabelText("Reference")).toHaveAccessibleDescription(
      expect.stringContaining("Type the reference this recommended step comes from."),
    );
    fireEvent.change(within(form).getByLabelText("Reference"), { target: { value: "IATA AHM 517" } });
    fireEvent.change(within(form).getByLabelText("Mechanism"), { target: { value: "rule_based" } });
    fireEvent.click(within(form).getByRole("button", { name: "Add step" }));
    await waitFor(() => expect(posted(api)).toHaveLength(1));
    expect(posted(api)[0]?.body).toMatchObject({
      kind: "decision",
      provenance: "R",
      segment_ids: [],
      r_reference: "IATA AHM 517",
      mechanism: "rule_based",
    });
  });

  it("shows the server's message under the field it names", async () => {
    addingBackend({
      status: 422,
      field: "label",
      message: "The name contains a name from your list of names to hide. Use the role instead.",
    });
    const form = await openAdd();
    fireEvent.change(within(form).getByLabelText("Name"), { target: { value: "Ask the lead" } });
    fireEvent.click(within(form).getByRole("radio", { name: "Recommended practice" }));
    fireEvent.change(within(form).getByLabelText("Reference"), { target: { value: "Handbook" } });
    fireEvent.click(within(form).getByRole("button", { name: "Add step" }));
    await waitFor(() =>
      expect(within(form).getByLabelText("Name")).toHaveAccessibleDescription(
        "The name contains a name from your list of names to hide. Use the role instead.",
      ),
    );
  });

  it("Esc leaves the picker, then discards the new step; selecting another step does too", async () => {
    const api = addingBackend();
    const form = await openAdd();
    fireEvent.click(within(form).getByRole("button", { name: "Pick a passage" }));
    await within(panel()).findByRole("list", { name: "Sources" });
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(await screen.findByRole("form", { name: "Add missing step" })).toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(screen.queryByRole("form", { name: "Add missing step" })).not.toBeInTheDocument();
    fireEvent.click(within(panel()).getByRole("button", { name: "Add a missing step after this one" }));
    await screen.findByRole("form", { name: "Add missing step" });
    fireEvent.click(screen.getByRole("button", { name: /^Activity, Issue load sheet/ }));
    expect(await within(panel()).findByRole("heading", { name: "Issue load sheet" })).toBeInTheDocument();
    expect(posted(api)).toEqual([]);
  });

  it("is not offered on the end", async () => {
    addingBackend();
    renderApp(`${PATH}?step=${elementByLabel("Final load sheet issued").id}`);
    expect(await screen.findByRole("button", { name: "Close details" })).toBeInTheDocument();
    expect(within(panel()).queryByRole("button", { name: "Add a missing step after this one" })).not.toBeInTheDocument();
  });

  it("has no serious accessibility problems in the form and the picker", async () => {
    addingBackend();
    const form = await openAdd();
    fireEvent.click(within(form).getByRole("button", { name: "Add step" }));
    expect(await seriousViolations(document.body)).toEqual([]);
    fireEvent.click(within(form).getByRole("button", { name: "Pick a passage" }));
    fireEvent.click(await within(panel()).findByRole("button", { name: /interview_transcript\.txt/ }));
    await within(panel()).findByRole("button", { name: "Use this passage, 06:40" });
    expect(await seriousViolations(document.body)).toEqual([]);
  });
});
