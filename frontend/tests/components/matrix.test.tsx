import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AlignmentTable } from "../../src/components/matrix";
import { divergenceCounts, filterRows, sortRows, type AlignmentRow } from "../../src/lib/matrix";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

function row(label: string, change: Partial<AlignmentRow> = {}): AlignmentRow {
  return {
    element_id: label.toLowerCase().replace(/\W+/g, "-"),
    label,
    kind: "activity",
    sop: "supports",
    interview: "supports",
    sme_official: "silent",
    sme_lived: "supports",
    jd: "silent",
    artefact: "not_applicable",
    state: "corroborated",
    divergence_types: [],
    ...change,
  };
}

// The sample's rows (the G4 baseline), in process order.
const ROWS: AlignmentRow[] = [
  row("Draft load plan", { jd: "supports" }),
  row("Approve load plan", {
    kind: "approval",
    interview: "silent",
    sme_lived: "silent",
    jd: "supports",
    state: "documented_only",
  }),
  row("Resolve or offload", {
    sop: "silent",
    sme_official: "account_unclear",
    sme_lived: "account_unclear",
    state: "practiced_only",
  }),
  row("Load and return LIR", { sop: "contradicts", state: "contested", divergence_types: ["threshold"] }),
  row("Deviation in limits?", {
    kind: "decision",
    sop: "contradicts",
    state: "contested",
    divergence_types: ["ownership"],
  }),
];

describe("sorting and filtering (lib/matrix)", () => {
  it("most serious first: disagreement, then one-sided accounts, then agreement; ties in process order", () => {
    expect(sortRows(ROWS, "severity").map((r) => r.label)).toEqual([
      "Load and return LIR",
      "Deviation in limits?",
      "Approve load plan",
      "Resolve or offload",
      "Draft load plan",
    ]);
    expect(sortRows(ROWS, "process")).toEqual(ROWS);
    const traced = row("Issue load sheet", { artefact: "contradicts", state: "trace_contradicted" });
    expect(sortRows([...ROWS, traced], "severity")[0]).toBe(traced);
  });

  it("filters by any chosen divergence type; none chosen shows every step", () => {
    expect(filterRows(ROWS, new Set())).toHaveLength(5);
    expect(filterRows(ROWS, new Set(["ownership"])).map((r) => r.label)).toEqual(["Deviation in limits?"]);
    expect(filterRows(ROWS, new Set(["ownership", "threshold"]))).toHaveLength(2);
    expect(Object.fromEntries(divergenceCounts(ROWS))).toEqual({ threshold: 1, ownership: 1 });
  });
});

describe("the alignment table", () => {
  it("every cell is a glyph with words; silence reads as silent, never as contradiction", async () => {
    const onOpen = vi.fn();
    const { container } = render(<AlignmentTable rows={ROWS} onOpen={onOpen} />);
    const table = screen.getByRole("table", { name: "How each kind of source stands on each step" });
    const headers = within(table).getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual([
      "Step",
      "SOP / manual",
      "SME official",
      "SME lived",
      "Job description",
      "Executed artefacts",
      "State",
      "Divergence",
    ]);
    const approve = within(table).getByRole("row", { name: /Approve load plan/ });
    const cells = within(approve).getAllByRole("cell").map((c) => c.textContent);
    expect(cells).toEqual([
      "Supports",
      "Silent",
      "Silent",
      "Supports",
      "No source of this kind",
      "Documented only",
      "None",
    ]);
    // P9u-2: the interview speaks of it, but in answers whose account is unclear: never guessed.
    const resolve = within(table).getByRole("row", { name: /Resolve or offload/ });
    expect(within(resolve).getAllByText("Account unclear")).toHaveLength(2);
    const lir = within(table).getByRole("row", { name: /Load and return LIR/ });
    expect(within(lir).getByText("Threshold")).toHaveClass("chip--danger");
    expect(within(lir).getByText("Contested").closest(".glyph")).toHaveClass("glyph--danger-text");
    fireEvent.click(within(lir).getByRole("button", { name: "Load and return LIR" }));
    expect(onOpen).toHaveBeenCalledWith("load-and-return-lir");
    fireEvent.click(within(approve).getByText("Documented only"));
    expect(onOpen).toHaveBeenLastCalledWith("approve-load-plan");
    expect(onOpen).toHaveBeenCalledTimes(2);
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("Matrix screen (PRD §5.4)", () => {
  const DRAFT = {
    id: "v2",
    engagement_id: "e1",
    label: "v0.1",
    state: "draft",
    created_at: "2026-09-28T09:00:00+00:00",
    published_at: null,
    published_by: null,
    parent_version_id: null,
  };
  const PUBLISHED = { ...DRAFT, id: "v1", label: "v1.0", state: "published", published_at: "2026-09-28T10:00:00+00:00" };

  function backend(versions: unknown[], matrix: unknown = ROWS) {
    return fakeApi({
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/versions": () => ({ body: versions }),
      "GET /api/versions/v2/alignment-matrix": () => ({ body: matrix }),
      "GET /api/versions/v1/alignment-matrix": () => ({ body: matrix }),
    });
  }

  it("shows the draft's matrix with divergence filters and sorting", async () => {
    const { calls } = backend([PUBLISHED, DRAFT]);
    const { container } = renderApp("/engagements/e1/matrix");
    const table = await screen.findByRole("table", { name: "How each kind of source stands on each step" });
    expect(calls.some((c) => c.key === "GET /api/versions/v2/alignment-matrix")).toBe(true);
    expect(screen.getByText(/of v0.1\. Sources are compared, never merged/)).toBeInTheDocument();
    expect(within(table).getAllByRole("row")).toHaveLength(6);
    const ownership = screen.getByRole("button", { name: "Ownership 1" });
    fireEvent.click(ownership);
    expect(ownership).toHaveAttribute("aria-pressed", "true");
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    expect(screen.getByText("1 of 5 steps have the chosen divergence.")).toBeInTheDocument();
    fireEvent.click(ownership);
    fireEvent.click(screen.getByRole("radio", { name: "Most serious first" }));
    const labels = within(table)
      .getAllByRole("rowheader")
      .map((h) => h.textContent);
    expect(labels[0]).toBe("Load and return LIR");
    fireEvent.click(screen.getByRole("button", { name: "Sequence 0" }));
    expect(screen.getByText(/No step has the chosen divergence/)).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("a row opens its step on Review", async () => {
    backend([DRAFT]);
    renderApp("/engagements/e1/matrix");
    fireEvent.click(await screen.findByRole("button", { name: "Resolve or offload" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Review" })).toBeInTheDocument();
  });

  it("without a draft it shows the latest published version, opening steps on Published", async () => {
    backend([PUBLISHED]);
    renderApp("/engagements/e1/matrix");
    expect(await screen.findByText(/of v1\.0 \(published\)/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Resolve or offload" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Published" })).toBeInTheDocument();
  });

  it("no draft yet: says so and links to Draft", async () => {
    backend([]);
    renderApp("/engagements/e1/matrix");
    expect(await screen.findByText(/No draft map yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Draft" })).toHaveAttribute("href", "/engagements/e1/draft");
  });

  it("a matrix that can't be loaded says so with Try again", async () => {
    fakeApi({
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/versions": () => ({ body: [DRAFT] }),
      "GET /api/versions/v2/alignment-matrix": () => ({
        status: 500,
        body: { error: { code: "INTERNAL", message: "Something broke.", details: {} } },
      }),
    });
    renderApp("/engagements/e1/matrix");
    expect(await screen.findByText("The matrix couldn't be loaded")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
