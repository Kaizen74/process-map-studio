import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MapLegend, MapStage, MapToolbar } from "../../src/components/map";
import { lensLine } from "../../src/lib/lens";
import { asView, ghostLabel, inView, variantFor } from "../../src/lib/views";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp } from "../renderApp";
import { SAMPLE, elementByLabel, graphFor, layoutFor } from "../sampleMap";

// PRD §3.12.11 and §5.7.3 (V2): the map drawn As done (default) or As documented, with Show the
// other view, "not described" connectors and the Work type lens. The backend lays out each view;
// these tests draw exactly what it serves (the sample's view layouts).

const VID = SAMPLE.graph.version.id;

describe("views (pure helpers)", () => {
  it("As done unless the address asks for As documented; membership decides what a view draws", () => {
    expect([asView(null), asView("documented"), asView("other")]).toEqual(["done", "documented", "done"]);
    const approve = elementByLabel("Approve load plan"); // documented only (A.9)
    const reading = elementByLabel("Read report at aircraft"); // in practice only
    expect([inView(approve, "done"), inView(approve, "documented")]).toEqual([false, true]);
    expect([inView(reading, "done"), inView(reading, "documented")]).toEqual([true, false]);
    expect(inView({ view_membership: null }, "documented")).toBe(true); // drafted before v1.10
    expect([ghostLabel("done"), ghostLabel("documented")]).toEqual([
      "only in the documented version",
      "only in practice",
    ]);
  });

  it("the lens line shows the active view's value where the views differ (A.9 variants)", () => {
    const lir = elementByLabel("Load and return LIR");
    expect(variantFor(lir, "documented")).toEqual({ time: "Within 10 minutes of loading completion" });
    expect(lensLine(lir, "plain", 0, "done")).toEqual({
      kind: "text",
      text: "Up to fifteen minutes' wait for the report",
      danger: false,
    });
    const deviation = elementByLabel("Deviation in limits?");
    expect(lensLine(deviation, "plain", 0, "documented")).toEqual({
      kind: "text",
      text: "Owner: Load control lead",
      danger: false,
    });
    // Other lenses are unchanged by the view.
    expect(lensLine(lir, "confidence", 0, "documented")).toEqual(lensLine(lir, "confidence", 0, "done"));
  });

  it("the Work type lens: glyph and word, 'proposed' until Eric confirms (A.8)", () => {
    expect(lensLine(elementByLabel("Deviation in limits?"), "work_type")).toEqual({
      kind: "work_type",
      type: "complex",
      label: "Complex",
      proposed: true,
    });
    expect(lensLine(elementByLabel("Resolve or offload"), "work_type")).toMatchObject({
      type: "not_classified",
      label: "Not classified",
    });
  });
});

describe("MapStage per view", () => {
  it("As done draws the steps done in practice; As documented the documents' steps", () => {
    const { container, rerender } = render(
      <MapStage graph={SAMPLE.graph} layout={SAMPLE.views.done} lens="plain" scale={1} selectedId={null} onSelect={vi.fn()} />,
    );
    const drawn = () => [...container.querySelectorAll("[data-node]")].map((n) => n.getAttribute("title"));
    expect(drawn()).not.toContain("Approve load plan");
    expect(drawn()).toContain("Read report at aircraft");
    rerender(
      <MapStage
        graph={SAMPLE.graph}
        layout={SAMPLE.views.documented}
        lens="plain"
        view="documented"
        scale={1}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );
    expect(drawn()).toContain("Approve load plan");
    expect(drawn()).not.toContain("Read report at aircraft");
  });

  it("Show the other view ghosts the other view's steps: their own label, no marker", async () => {
    const { container } = render(
      <MapStage
        graph={SAMPLE.graph}
        layout={SAMPLE.views.done_with_other}
        lens="plain"
        scale={1}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );
    const approve = elementByLabel("Approve load plan");
    const ghost = container.querySelector(`[data-node="${approve.id}"]`);
    expect(ghost).toHaveClass("map-node--ghost");
    expect(ghost?.getAttribute("aria-label")).toMatch(/, only in the documented version$/);
    expect(ghost?.querySelectorAll(".map-marker")).toHaveLength(0);
    expect(screen.getByText("only in the documented version")).toBeInTheDocument();
    const ghostLines = SAMPLE.views.done_with_other.edges.filter((e) => e.ghost).map((e) => e.id);
    expect(ghostLines.length).toBeGreaterThan(0);
    for (const id of ghostLines) expect(container.querySelector(`[data-edge="${id}"]`)).toHaveClass("map-edge--ghost");
    expect(await seriousViolations(container)).toEqual([]);
  });

  it('a "not described" connector is dashed and labelled (A.9: none on the sample, so one is made)', () => {
    const first = SAMPLE.views.done.edges.find((e) => e.label_pos !== null);
    if (!first) throw new Error("no labelled edge");
    const edges = SAMPLE.views.done.edges.map((e) => (e.id === first.id ? { ...e, kind: "gap", label: "Not described" } : e));
    const layout = { ...SAMPLE.views.done, edges };
    const { container } = render(
      <MapStage graph={SAMPLE.graph} layout={layout} lens="plain" scale={1} selectedId={null} onSelect={vi.fn()} />,
    );
    const line = container.querySelector(`[data-edge="${first.id}"]`);
    expect(line).toHaveClass("map-edge--gap");
    expect(within(line as HTMLElement).getByText("Not described")).toBeInTheDocument();
  });

  it("the Work type lens draws a glyph and a word under each step, adding no marker", () => {
    const { container } = render(
      <MapStage graph={SAMPLE.graph} layout={SAMPLE.views.done} lens="work_type" scale={1} selectedId={null} onSelect={vi.fn()} />,
    );
    expect(container.querySelectorAll('[data-lens="work_type"]').length).toBeGreaterThan(0);
    expect(screen.getAllByText("Complex").length).toBe(1); // Deviation in limits?
    expect(screen.getAllByText("proposed").length).toBeGreaterThan(0);
    const plain = render(
      <MapStage graph={SAMPLE.graph} layout={SAMPLE.views.done} lens="plain" scale={1} selectedId={null} onSelect={vi.fn()} />,
    );
    expect(container.querySelectorAll(".map-marker").length).toBe(plain.container.querySelectorAll(".map-marker").length);
  });
});

describe("legend and toolbar", () => {
  it('the legend shows "Not described" As done only, ghosted steps when shown, and the work type key', () => {
    const { rerender } = render(<MapLegend lens="plain" view="done" />);
    expect(screen.getByText(/Not described/)).toBeInTheDocument();
    expect(screen.queryByText("Only in the documented version")).not.toBeInTheDocument();
    rerender(<MapLegend lens="work_type" view="documented" showOther />);
    expect(screen.queryByText(/Not described/)).not.toBeInTheDocument();
    expect(screen.getByText("Only in practice")).toBeInTheDocument();
    const key = screen.getByRole("list", { name: "Lens key" });
    const items = within(key).getAllByRole("listitem");
    ["Clear", "Complicated", "Complex", "Chaotic", "Confused", "Not classified"].forEach((label, i) =>
      expect(items[i]).toHaveTextContent(new RegExp(`${label}$`)),
    );
    expect(items).toHaveLength(6);
  });

  it("the toolbar switches the view and the other view, and offers the Work type lens", () => {
    const onAsView = vi.fn();
    const onShowOther = vi.fn();
    render(
      <MapToolbar
        view="map"
        onView={vi.fn()}
        lens="plain"
        onLens={vi.fn()}
        asView="done"
        onAsView={onAsView}
        showOther={false}
        onShowOther={onShowOther}
        zoom="fit"
        onZoom={vi.fn()}
        steps={9}
        lanes={5}
        phases={3}
        large={false}
      />,
    );
    const views = screen.getByRole("radiogroup", { name: "View" });
    expect(within(views).getByRole("radio", { name: "As done" })).toHaveAttribute("aria-checked", "true");
    fireEvent.click(within(views).getByRole("radio", { name: "As documented" }));
    expect(onAsView).toHaveBeenCalledWith("documented");
    fireEvent.click(screen.getByRole("checkbox", { name: "Show the other view" }));
    expect(onShowOther).toHaveBeenCalledWith(true);
    expect(within(screen.getByRole("radiogroup", { name: "Lens" })).getByRole("radio", { name: "Work type" })).toBeInTheDocument();
  });
});

describe("Review screen with the views (PRD §5.7.3)", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  function backend() {
    return fakeApi({
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/draft": () => ({
        body: { job: null, version: { id: VID, engagement_id: "e1", label: "v0.1", state: "draft",
          created_at: "2026-09-27T10:00:00+00:00" }, summary: null }, // prettier-ignore
      }),
      [`GET /api/versions/${VID}/graph`]: (_body, url) => ({ body: graphFor(url) }),
      [`GET /api/versions/${VID}/layout`]: (_body, url) => ({ body: layoutFor(url) }),
      ...Object.fromEntries(
        Object.entries(SAMPLE.elements).map(([id, element]) => [`GET /api/elements/${id}`, () => ({ body: element })]),
      ),
    });
  }

  it("opens As done; As documented and Show the other view ask the backend for that layout", async () => {
    const { calls } = backend();
    renderApp("/engagements/e1/review");
    expect(await screen.findByRole("radio", { name: "As done" })).toHaveAttribute("aria-checked", "true");
    const layouts = () => calls.filter((c) => c.key === `GET /api/versions/${VID}/layout`).length;
    expect(screen.queryByRole("button", { name: /^Approval, Approve load plan/ })).not.toBeInTheDocument();
    const before = layouts();
    fireEvent.click(screen.getByRole("radio", { name: "As documented" }));
    expect(await screen.findByRole("button", { name: /^Approval, Approve load plan/ })).toBeInTheDocument();
    expect(layouts()).toBeGreaterThan(before);
    fireEvent.click(screen.getByRole("radio", { name: "As done" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Show the other view" }));
    expect(await screen.findByRole("button", { name: /Approve load plan.*only in the documented version$/ })).toBeInTheDocument();
  });

  it("choosing a step only in the other view shows that view, so no step is out of reach", async () => {
    backend();
    renderApp("/engagements/e1/review");
    const approve = elementByLabel("Approve load plan");
    const segment = await screen.findByRole("button", { name: `${approve.label}, not reviewed yet` });
    fireEvent.click(segment);
    await waitFor(() => expect(screen.getByRole("radio", { name: "As documented" })).toHaveAttribute("aria-checked", "true"));
    expect(await screen.findByRole("button", { name: /^Approval, Approve load plan/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Approve load plan" })).toBeInTheDocument(); // its panel
  });
});
