// Review rules shared by the Review screen (PRD §5.6–§5.7). Pure functions.

import type { Graph } from "./mapTypes";

const STEPS = new Set(["activity", "decision", "approval"]);

/** The step to look at first: one the verifier only partly supported, else the first unreviewed. */
export function firstNeedingAttention(graph: Graph): string | null {
  const open = graph.elements.filter((e) => STEPS.has(e.kind) && e.review_status === "draft");
  return (open.find((e) => e.needs_check) ?? open[0] ?? null)?.id ?? null;
}
