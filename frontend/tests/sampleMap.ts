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
}

export const SAMPLE: SampleMap = JSON.parse(
  readFileSync(join(__dirname, "fixtures", "sample_map.json"), "utf-8"),
) as SampleMap;

export function elementByLabel(label: string) {
  const element = SAMPLE.graph.elements.find((e) => e.label === label);
  if (!element) throw new Error(`no element ${label}`);
  return element;
}
