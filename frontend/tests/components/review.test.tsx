import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftState } from "../../src/api/types";
import { firstNeedingAttention } from "../../src/lib/review";
import { fitScale } from "../../src/features/review/useFitScale";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp } from "../renderApp";
import { SAMPLE, elementByLabel } from "../sampleMap";

const VID = SAMPLE.graph.version.id;
const PATH = "/engagements/e1/review";

const DRAFTED: DraftState = {
  job: null,
  version: { id: VID, engagement_id: "e1", label: "v0.1", state: "draft", created_at: "2026-09-27T10:00:00+00:00" },
  summary: { steps: 8, needs_check: 0, verified: 21, rejected: 0, open_questions: 5, scrubbed: 0 },
};

function backend(draft: DraftState = DRAFTED) {
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: { ...ENGAGEMENT, trigger: "Flight scheduled" } }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/draft": () => ({ body: draft }),
    [`GET /api/versions/${VID}/graph`]: () => ({ body: SAMPLE.graph }),
    [`GET /api/versions/${VID}/layout`]: () => ({ body: SAMPLE.layout }),
    ...Object.fromEntries(
      Object.entries(SAMPLE.elements).map(([id, element]) => [`GET /api/elements/${id}`, () => ({ body: element })]),
    ),
    ...Object.fromEntries(
      Object.entries(SAMPLE.segments).flatMap(([id, page]) => [
        [`GET /api/sources/${id}/segments`, () => ({ body: page })],
        [
          `GET /api/sources/${id}`,
          () => ({ body: { id, kind: "sop", format: "docx", version_date: "2025-03-01", controlled_copy: true } }),
        ],
      ]),
    ),
  });
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("Review screen (PRD §5.6)", () => {
  it("shows the banner with read-only progress, the header strip and the map", async () => {
    backend();
    renderApp(PATH);
    expect(await screen.findByText("Draft v0.1")).toBeInTheDocument();
    expect(screen.getByText(/Generated from 5 sources/)).toBeInTheDocument();
    expect(screen.getByText(/steps reviewed/)).toHaveTextContent("0 of 10 steps reviewed");
    const progress = screen.getByRole("list", { name: /Review progress/ });
    expect(within(progress).getAllByRole("button")).toHaveLength(10); // v1.10 A.5: ten steps
    const strip = screen.getByRole("region", { name: "Process at a glance" });
    expect(within(strip).getByText("Flight scheduled")).toBeInTheDocument();
    expect(within(strip).getByText("~75 min elapsed, ~60 min work")).toBeInTheDocument();
    expect(within(strip).getByText("Incomplete: 3 steps without time")).toBeInTheDocument(); // v1.10: + Read report at aircraft
    expect(within(strip).getByText("Not stated")).toBeInTheDocument(); // no process KPI
    expect(screen.getByText("10 steps · 5 lanes · 3 phases")).toBeInTheDocument(); // v1.10 A.5
    expect(screen.getAllByRole("button", { name: /^(Activity|Decision|Approval|Start|End),/ })).toHaveLength(12);
    expect(screen.getByRole("heading", { name: "How to review" })).toBeInTheDocument();
  });

  it("selects a step from the map or the progress bar and shows its header", async () => {
    backend();
    renderApp(PATH);
    fireEvent.click(await screen.findByRole("button", { name: /^Activity, Load and return LIR/ }));
    const panel = screen.getByRole("complementary", { name: "Step details" });
    expect(within(panel).getByRole("heading", { name: "Load and return LIR" })).toBeInTheDocument();
    expect(within(panel).getByText("Activity · Check and load")).toBeInTheDocument();
    expect(within(panel).getByText("Lane · Ramp")).toBeInTheDocument();
    expect(within(panel).getByText("Contested")).toHaveClass("chip--danger");
    expect(within(panel).getByText("Divergence · threshold")).toHaveClass("chip--danger");
    expect(within(panel).getByText("Unreviewed")).toHaveClass("chip--dashed");
    fireEvent.click(screen.getByRole("button", { name: "Approve deviation, not reviewed yet" }));
    expect(within(panel).getByRole("heading", { name: "Approve deviation" })).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole("button", { name: "Close details" }));
    expect(screen.getByRole("heading", { name: "How to review" })).toBeInTheDocument();
  });

  it("shows the selected step's evidence and details, read-only", async () => {
    backend();
    renderApp(PATH);
    fireEvent.click(await screen.findByRole("button", { name: /^Decision, Deviation in limits\?/ }));
    const panel = screen.getByRole("complementary", { name: "Step details" });
    const evidence = await within(panel).findByRole("region", { name: "Evidence" });
    expect(within(evidence).getAllByRole("button")).toHaveLength(2); // two cited passages
    expect(within(evidence).getAllByText(/Silence is not contradiction/)).toHaveLength(3);
    expect(within(panel).getAllByText("A?")).toHaveLength(2);
    expect(within(panel).getByRole("region", { name: "Decision rights and mechanism" })).toBeInTheDocument();
    expect(within(panel).getByRole("region", { name: "How confidence was computed" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Confirm as drafted" })).toBeInTheDocument(); // P6
  });

  it("opens a piece of evidence at its passage with the quote highlighted, and goes back", async () => {
    backend();
    renderApp(PATH);
    fireEvent.click(await screen.findByRole("button", { name: /^Activity, Load and return LIR/ }));
    fireEvent.click(await screen.findByRole("button", { name: /Open sop_RP-02.docx at §2/ }));
    const panel = await screen.findByRole("complementary", { name: "Source" });
    expect(await within(panel).findByRole("heading", { name: "sop_RP-02.docx" })).toBeInTheDocument();
    expect(within(panel).getByText("docx · version 2025-03-01 · controlled copy")).toBeInTheDocument();
    const target = panel.querySelector('[aria-current="true"]');
    expect(target).toHaveClass("viewer-passage--target");
    expect(target?.querySelector("mark")?.textContent).toBe(
      "The Ramp Supervisor shall return the loading report to Load Control within 10 minutes of loading completion.",
    );
    expect(within(panel).getByText(/Speaker names are replaced by roles/)).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole("button", { name: "← Back to Load and return LIR" }));
    expect(await screen.findByRole("region", { name: "Evidence" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Open interview_transcript.txt at 21:50/ }));
    expect(await screen.findByRole("complementary", { name: "Source" })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(await screen.findByRole("complementary", { name: "Step details" })).toBeInTheDocument();
  });

  it("the RACI matrix marks a disputed accountable role and selects a step by row", async () => {
    backend();
    renderApp(PATH);
    const matrix = await screen.findByRole("table");
    expect(within(matrix).getByText(/means the sources disagree about who is accountable/)).toBeInTheDocument();
    const row = within(matrix).getByRole("button", { name: "Deviation in limits?" }).closest("tr");
    expect(row).not.toBeNull();
    const contested = within(row as HTMLElement).getAllByText("A?");
    expect(contested).toHaveLength(2);
    expect(contested[0]).toHaveClass("raci__contested");
    expect(within(matrix).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Step",
      "Load control lead",
      "Airline ops",
      "Captain",
      "Load controller",
      "Ramp",
    ]);
    fireEvent.click(row as HTMLElement);
    expect(screen.getByRole("complementary", { name: "Step details" })).toBeInTheDocument();
    expect(row).toHaveClass("raci__row--selected");
  });

  it("start and end explain they come from the scope, without evidence", async () => {
    backend();
    renderApp(PATH);
    fireEvent.click(await screen.findByRole("button", { name: "Start, Flight scheduled" }));
    expect(screen.getByText(/Where the process starts, from the engagement's scope/)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Evidence" })).toBeNull();
  });

  it("starts with the first step that needs attention", async () => {
    backend();
    renderApp(PATH);
    fireEvent.click(await screen.findByRole("button", { name: "Start with the first step that needs attention" }));
    expect(screen.getByRole("heading", { name: "Draft load plan" })).toBeInTheDocument();
    const withCheck = {
      ...SAMPLE.graph,
      elements: SAMPLE.graph.elements.map((e) => (e.label === "Deviation in limits?" ? { ...e, needs_check: true } : e)),
    };
    expect(firstNeedingAttention(withCheck)).toBe(elementByLabel("Deviation in limits?").id);
  });

  it("opens with a step selected from the address", async () => {
    backend();
    renderApp(`${PATH}?step=${elementByLabel("Issue load sheet").id}`);
    expect(await screen.findByRole("heading", { name: "Issue load sheet" })).toBeInTheDocument();
  });

  it("fits the map to the card once it has loaded, and shows it at 100% on request", async () => {
    const width = vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(834);
    try {
      backend();
      const { container } = renderApp(PATH);
      await screen.findByText("Draft v0.1");
      const stage = container.querySelector<HTMLElement>(".map-stage");
      expect(stage?.style.transform).toBe(`scale(${834 / SAMPLE.layout.canvas.w})`);
      fireEvent.click(screen.getByRole("radio", { name: "100%" }));
      expect(container.querySelector<HTMLElement>(".map-stage")?.style.transform).toBe("scale(1)");
    } finally {
      width.mockRestore();
    }
  });

  it("remembers the lens in this browser", async () => {
    backend();
    const view = renderApp(PATH);
    fireEvent.click(await screen.findByRole("radio", { name: "Source state" }));
    expect(window.localStorage.getItem("pms.lens")).toBe("source_state");
    expect(screen.getByRole("list", { name: "Lens key" })).toBeInTheDocument();
    view.unmount();
    renderApp(PATH);
    expect(await screen.findByRole("radio", { name: "Source state" })).toHaveAttribute("aria-checked", "true");
  });

  it("says when there is no draft yet, or one is being made", async () => {
    backend({ job: null, version: null, summary: null });
    const view = renderApp(PATH);
    expect(await screen.findByText(/There is no draft map to review yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Draft" })).toHaveAttribute("href", "/engagements/e1/draft");
    view.unmount();
    vi.unstubAllGlobals();
    backend({ job: { status: "running" } as DraftState["job"], version: null, summary: null });
    renderApp(PATH);
    expect(await screen.findByText(/A draft map is being made/)).toBeInTheDocument();
  });

  it("explains a failed load with Try again", async () => {
    fakeApi({
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/draft": () => ({ body: DRAFTED }),
      [`GET /api/versions/${VID}/graph`]: () => ({
        status: 500,
        body: { error: { code: "INTERNAL", message: "Something went wrong.", details: {} } },
      }),
      [`GET /api/versions/${VID}/layout`]: () => ({ body: SAMPLE.layout }),
    });
    renderApp(PATH);
    expect(await screen.findByText("The map couldn't be loaded")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("has no serious accessibility problems, with and without a selection", async () => {
    backend();
    const { container } = renderApp(PATH);
    await screen.findByText("Draft v0.1");
    expect(await seriousViolations(container)).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: /^Decision, Deviation in limits\?/ }));
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("Fit (PRD §5.5)", () => {
  it("is min(1, container / canvas), never below 0.5", () => {
    expect(fitScale(2000, 1112)).toBe(1);
    expect(fitScale(834, 1112)).toBeCloseTo(0.75);
    expect(fitScale(300, 1112)).toBe(0.5);
    expect(fitScale(0, 1112)).toBe(1); // not measured yet
  });
});
