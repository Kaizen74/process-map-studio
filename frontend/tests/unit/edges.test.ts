import { describe, expect, it } from "vitest";
import { arrowhead, edgeSegments } from "../../src/lib/edges";
import type { Point } from "../../src/lib/mapTypes";
import { SAMPLE, elementByLabel } from "../sampleMap";

function route(from: string, to: string): Point[] {
  const a = elementByLabel(from).id;
  const b = elementByLabel(to).id;
  const edge = SAMPLE.graph.edges.find((e) => e.from === a && e.to === b);
  const drawn = SAMPLE.layout.edges.find((e) => e.id === edge?.id);
  if (!drawn) throw new Error("no edge");
  return drawn.points;
}

describe("edge segments and arrowheads (PRD §5.5, all four routes of §3.9)", () => {
  it("same lane: one horizontal run, arrow pointing right", () => {
    const points = route("Deviation in limits?", "Issue load sheet");
    // v1.10 A.5: two more columns before the deviation check (Busy wave?, Read report at aircraft).
    expect(edgeSegments(points)).toEqual([{ x: 1076, y: 464, length: 48, orientation: "horizontal" }]);
    expect(arrowhead(points)).toEqual({ x: 1124, y: 464, direction: "right" });
  });

  it("another lane: along, through the gutter, along", () => {
    const points = route("Draft load plan", "Approve load plan");
    expect(edgeSegments(points).map((s) => s.orientation)).toEqual(["horizontal", "vertical", "horizontal"]);
    const [, up] = edgeSegments(points);
    expect(up).toEqual({ x: 368, y: 92, length: 372, orientation: "vertical" });
    expect(arrowhead(points)?.direction).toBe("right");
  });

  it("exception step above its decision: one vertical run, arrow pointing up", () => {
    const points = route("Special loads OK?", "Resolve or offload");
    expect(edgeSegments(points)).toEqual([{ x: 554, y: 238, length: 200, orientation: "vertical" }]);
    expect(arrowhead(points)).toEqual({ x: 554, y: 238, direction: "up" });
  });

  it("back edge: up to the track, across, down into the target's top", () => {
    const points = route("Approve deviation", "Load and return LIR");
    expect(edgeSegments(points).map((s) => [s.orientation, s.length])).toEqual([
      ["vertical", 8],
      ["horizontal", 372], // three columns back since v1.10 A.5
      ["vertical", 256],
    ]);
    expect(arrowhead(points)).toEqual({ x: 678, y: 566, direction: "down" });
  });

  it("an arrow points left or down for lines that travel that way; repeated points are skipped", () => {
    const left: Point[] = [
      [100, 10],
      [40, 10],
      [40, 10],
    ];
    expect(edgeSegments(left)).toEqual([{ x: 40, y: 10, length: 60, orientation: "horizontal" }]);
    expect(arrowhead(left)).toEqual({ x: 40, y: 10, direction: "left" });
    expect(arrowhead([[5, 5]])).toBeNull();
  });
});
