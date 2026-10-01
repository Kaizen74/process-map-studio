import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MapLegend, MapStage, MapToolbar } from "../../src/components/map";
import { LENSES, type Lens } from "../../src/lib/lens";
import { seriousViolations } from "../axe";
import { SAMPLE, elementByLabel } from "../sampleMap";

function draw(lens: Lens = "plain", selectedId: string | null = null, onSelect = vi.fn()) {
  return render(
    <MapStage
      graph={SAMPLE.graph}
      layout={SAMPLE.layout}
      lens={lens}
      scale={1}
      selectedId={selectedId}
      onSelect={onSelect}
    />,
  );
}

describe("MapStage (PRD §5.5)", () => {
  it("draws every node as a named button, in process order", () => {
    draw();
    const buttons = screen.getAllByRole("button");
    expect(buttons.map((b) => b.getAttribute("aria-label"))).toEqual(
      SAMPLE.graph.elements.map((e) => expect.stringContaining(e.label)),
    );
    expect(buttons[1]).toHaveAccessibleName("Activity, Draft load plan, Load controller, corroborated, unreviewed");
  });

  it("puts every node exactly where the layout says", () => {
    const { container } = draw();
    const plan = elementByLabel("Draft load plan");
    const node = SAMPLE.layout.nodes.find((n) => n.id === plan.id);
    const button = container.querySelector<HTMLElement>(`[data-node="${plan.id}"]`);
    expect(button?.style.left).toBe(`${node?.x}px`);
    expect(button?.style.top).toBe(`${node?.y}px`);
    expect(button?.style.width).toBe(`${node?.w}px`);
  });

  it("labels each lane with its role and step count", () => {
    draw();
    expect(screen.getByRole("group", { name: "Load controller lane, 6 steps" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Ramp lane, 1 step" })).toBeInTheDocument();
  });

  it("selects a node on click and highlights the lines touching it", () => {
    const onSelect = vi.fn();
    const plan = elementByLabel("Draft load plan");
    const { container, rerender } = draw("plain", null, onSelect);
    fireEvent.click(screen.getByRole("button", { name: /Draft load plan/ }));
    expect(onSelect).toHaveBeenCalledWith(plan.id);
    rerender(
      <MapStage graph={SAMPLE.graph} layout={SAMPLE.layout} lens="plain" scale={1} selectedId={plan.id} onSelect={onSelect} />,
    );
    // The lines drawn (the graph also lists lines for one view only, drawn per view from V1).
    const drawn = new Set(SAMPLE.layout.edges.map((e) => e.id));
    const touching = SAMPLE.graph.edges
      .filter((e) => (e.from === plan.id || e.to === plan.id) && drawn.has(e.id))
      .map((e) => e.id);
    const active = [...container.querySelectorAll(".map-edge--active")].map((e) => e.getAttribute("data-edge"));
    expect(active.sort()).toEqual(touching.sort());
    expect(screen.getByRole("button", { name: /Draft load plan/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("draws back edges dashed and every labelled exit with its label", () => {
    const { container } = draw();
    expect(container.querySelectorAll(".map-edge--back")).toHaveLength(3);
    const labels = [...container.querySelectorAll(".map-edge__label")].map((l) => l.textContent);
    expect(labels).toEqual(expect.arrayContaining(["Yes", "No", "Approve", "Rework", "Re-plan", "Re-trim"]));
    expect(container.querySelectorAll(".map-edge__arrow")).toHaveLength(SAMPLE.layout.edges.length);
  });

  it("each lens changes only the line under the nodes, never the markers (at most three)", () => {
    const counts: string[] = [];
    for (const { value } of LENSES) {
      const { container, unmount } = draw(value);
      const nodes = [...container.querySelectorAll(".map-node")];
      const markers = nodes.map(
        (n) => n.querySelectorAll(".map-marker").length + (n.classList.contains("map-node--unreviewed") ? 1 : 0),
      );
      expect(Math.max(...markers)).toBeLessThanOrEqual(3);
      counts.push(markers.join(","));
      unmount();
    }
    expect(new Set(counts).size).toBe(1);
  });

  it("shows each lens's line: time, state, confidence, time bars", () => {
    const lir = elementByLabel("Load and return LIR");
    let view = draw("plain");
    // V2: the loading step shows the As done value where the views differ (A.9 variants).
    expect(within(view.container).getByText("Up to fifteen minutes' wait for the report")).toBeInTheDocument();
    expect(within(view.container).getByText("~20 min")).toBeInTheDocument();
    expect(within(view.container).getAllByText("No time stated")[0]).toHaveClass("map-lens__danger");
    view.unmount();
    view = draw("source_state");
    expect(within(view.container).getAllByText("Contested").length).toBe(2);
    view.unmount();
    view = draw("confidence");
    expect(within(view.container).getAllByText("0.60")[0]).not.toHaveClass("map-lens__danger"); // not below 0.60
    expect(within(view.container).getAllByText("0.85")[0]).toBeInTheDocument();
    view.unmount();
    const low = {
      ...SAMPLE.graph,
      elements: SAMPLE.graph.elements.map((e) => (e.id === lir.id ? { ...e, confidence: 0.45 } : e)),
    };
    view = render(<MapStage graph={low} layout={SAMPLE.layout} lens="confidence" scale={1} selectedId={null} onSelect={vi.fn()} />);
    expect(within(view.container).getByText("0.45")).toHaveClass("map-lens__danger");
    expect(view.container.querySelector(".map-bar__fill--low")).not.toBeNull();
    view.unmount();
    view = draw("time");
    expect(within(view.container).getByText("40 + 15")).toBeInTheDocument();
    view.unmount();
  });

  it("shows the key-constraint marker and the unreviewed outline", () => {
    const { container } = draw();
    const lir = container.querySelector(`[data-node="${elementByLabel("Load and return LIR").id}"]`);
    expect(lir?.querySelector(".map-marker--constraint")).not.toBeNull();
    expect(lir).toHaveClass("map-node--unreviewed");
    expect(container.querySelectorAll(".map-marker--images")).toHaveLength(0); // images arrive in P8
  });

  it("fades a rejected step, strikes its label and fades its lines", () => {
    const plan = elementByLabel("Draft load plan");
    const graph = {
      ...SAMPLE.graph,
      elements: SAMPLE.graph.elements.map((e) => (e.id === plan.id ? { ...e, review_status: "rejected" } : e)),
    };
    const { container } = render(
      <MapStage graph={graph} layout={SAMPLE.layout} lens="plain" scale={1} selectedId={null} onSelect={vi.fn()} />,
    );
    expect(container.querySelector(`[data-node="${plan.id}"]`)).toHaveClass("map-node--rejected");
    // A.10 (C3): + the plan's hand-over to loading, stitched across the interviews.
    expect(container.querySelectorAll(".map-edge.map-faded").length).toBe(5);
  });

  it("scales the stage from the top-left", () => {
    const { container } = render(
      <MapStage graph={SAMPLE.graph} layout={SAMPLE.layout} lens="plain" scale={0.5} selectedId={null} onSelect={vi.fn()} />,
    );
    const viewport = container.querySelector<HTMLElement>(".map-viewport");
    expect(viewport?.style.width).toBe(`${SAMPLE.layout.canvas.w / 2}px`);
    expect(container.querySelector<HTMLElement>(".map-stage")?.style.transform).toBe("scale(0.5)");
  });

  it("has no serious accessibility problems", async () => {
    const { container } = draw("source_state");
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("MapToolbar and MapLegend", () => {
  it("switch lens and zoom, and warn about a large map in text", () => {
    const onLens = vi.fn();
    const onZoom = vi.fn();
    const props = { view: "map" as const, onView: vi.fn(), lens: "plain" as Lens, onLens, zoom: "fit" as const, onZoom, steps: 8, lanes: 5, phases: 3 };
    const { rerender } = render(<MapToolbar {...props} large={false} />);
    expect(screen.getByText("8 steps · 5 lanes · 3 phases")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Confidence" }));
    expect(onLens).toHaveBeenCalledWith("confidence");
    fireEvent.click(screen.getByRole("radio", { name: "100%" }));
    expect(onZoom).toHaveBeenCalledWith("full");
    rerender(<MapToolbar {...props} steps={30} large />);
    expect(screen.getByText(/Large map: consider splitting by phase/)).toHaveClass("map-toolbar__counts--large");
  });

  it("switches between map and table; the table leaves out lens and zoom; More offers Add missing step", () => {
    const onView = vi.fn();
    const onAddStep = vi.fn();
    const props = { onView, lens: "plain" as Lens, onLens: vi.fn(), zoom: "fit" as const, onZoom: vi.fn(), steps: 8, lanes: 5, phases: 3, large: false };
    const { rerender } = render(<MapToolbar {...props} view="map" />);
    expect(screen.queryByRole("button", { name: "More" })).toBeNull(); // not offered: can't change
    fireEvent.click(screen.getByRole("radio", { name: "Table" }));
    expect(onView).toHaveBeenCalledWith("table");
    rerender(<MapToolbar {...props} view="table" onAddStep={onAddStep} />);
    expect(screen.queryByRole("radiogroup", { name: "Lens" })).toBeNull();
    expect(screen.queryByRole("radiogroup", { name: "Zoom" })).toBeNull();
    expect(screen.getByText("8 steps · 5 lanes · 3 phases")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "More" }));
    fireEvent.click(within(screen.getByRole("dialog", { name: "More" })).getByRole("button", { name: "Add missing step" }));
    expect(onAddStep).toHaveBeenCalled();
    expect(screen.queryByRole("dialog", { name: "More" })).toBeNull();
  });

  it("the legend always lists shapes and markers, plus the active lens's key", () => {
    const { rerender } = render(<MapLegend lens="plain" />);
    for (const item of ["Activity", "Decision", "Approval", "Start / end", "Key constraint", "Has images", "Unreviewed", "Rework path"]) {
      expect(screen.getByText(item)).toBeInTheDocument();
    }
    expect(screen.queryByRole("list", { name: "Lens key" })).toBeNull();
    rerender(<MapLegend lens="source_state" />);
    expect(within(screen.getByRole("list", { name: "Lens key" })).getByText("Practiced only")).toBeInTheDocument();
    rerender(<MapLegend lens="time" />);
    expect(screen.getByText("Wait (hatched)")).toBeInTheDocument();
  });
});
