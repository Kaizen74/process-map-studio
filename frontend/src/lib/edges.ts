// Edge drawing (PRD §5.5): the backend gives each edge's corner points (§3.9); this turns them
// into straight segments (drawn as zero-width or zero-height bordered divs) and the arrowhead at
// the target. Pure and unit-tested; nothing here decides where a line goes.

import type { Point } from "../api/types";

export interface EdgeSegment {
  /** Top-left corner of the segment's box. */
  x: number;
  y: number;
  /** Length along the segment; the other dimension is 0. */
  length: number;
  orientation: "horizontal" | "vertical";
}

export type ArrowDirection = "right" | "left" | "up" | "down";

export interface Arrowhead {
  /** The tip, where the line meets the target. */
  x: number;
  y: number;
  direction: ArrowDirection;
}

/** Straight runs between consecutive corners; zero-length runs are dropped. */
export function edgeSegments(points: readonly Point[]): EdgeSegment[] {
  const out: EdgeSegment[] = [];
  for (let i = 1; i < points.length; i += 1) {
    const [x1, y1] = points[i - 1] as Point;
    const [x2, y2] = points[i] as Point;
    if (y1 === y2 && x1 !== x2) {
      out.push({ x: Math.min(x1, x2), y: y1, length: Math.abs(x2 - x1), orientation: "horizontal" });
    } else if (x1 === x2 && y1 !== y2) {
      out.push({ x: x1, y: Math.min(y1, y2), length: Math.abs(y2 - y1), orientation: "vertical" });
    }
  }
  return out;
}

/** The arrowhead at the last point, pointing the way the last run travels. */
export function arrowhead(points: readonly Point[]): Arrowhead | null {
  for (let i = points.length - 1; i > 0; i -= 1) {
    const [x1, y1] = points[i - 1] as Point;
    const [x2, y2] = points[i] as Point;
    if (x1 === x2 && y1 === y2) continue;
    const [tipX, tipY] = points[points.length - 1] as Point;
    const direction: ArrowDirection =
      y1 === y2 ? (x2 > x1 ? "right" : "left") : y2 > y1 ? "down" : "up";
    return { x: tipX, y: tipY, direction };
  }
  return null;
}
