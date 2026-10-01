// The illustrative Appendix A draft map (not SATS data) exactly as the backend serves it: graph,
// layout, every step's panel details and the cited sources' passages, with one set of stable IDs.
// Written by the backend test test_the_frontend_sample_matches_the_backend (PMS_UPDATE_GOLDEN=1).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { SegmentPage } from "../src/api/types";
import type { ElementDetail, Graph, Layout } from "../src/lib/mapTypes";

export interface SampleMap {
  graph: Graph;
  layout: Layout;
  elements: Record<string, ElementDetail>;
  segments: Record<string, SegmentPage>;
  /** V2 (§3.12.11): each view's layout, and As done with the documented-only steps ghosted. */
  views: { done: Layout; documented: Layout; done_with_other: Layout };
  view_graphs: { done: Graph; documented: Graph };
}

export const SAMPLE: SampleMap = JSON.parse(
  readFileSync(join(__dirname, "fixtures", "sample_map.json"), "utf-8"),
) as SampleMap;

export function elementByLabel(label: string) {
  const element = SAMPLE.graph.elements.find((e) => e.label === label);
  if (!element) throw new Error(`no element ${label}`);
  return element;
}

/** The layout the backend serves for a request URL (`?view=…&show_other=1`; none: combined). */
export function layoutFor(url: string): Layout {
  const query = new URLSearchParams(url.split("?")[1] ?? "");
  const view = query.get("view");
  if (view === "documented") return SAMPLE.views.documented;
  if (view === "done") return query.get("show_other") ? SAMPLE.views.done_with_other : SAMPLE.views.done;
  return SAMPLE.layout;
}

/** The graph the backend serves for a request URL (`?view=…`; none: every step and line). */
export function graphFor(url: string): Graph {
  const view = new URLSearchParams(url.split("?")[1] ?? "").get("view");
  return view === "done" || view === "documented" ? SAMPLE.view_graphs[view] : SAMPLE.graph;
}
