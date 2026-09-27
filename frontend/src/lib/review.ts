// Review rules shared by the Review screen (PRD §5.6–§5.7). Pure functions.

import type { Graph } from "./mapTypes";

const STEPS = new Set(["activity", "decision", "approval"]);

/** The step to look at first: one the verifier only partly supported, else the first unreviewed. */
export function firstNeedingAttention(graph: Graph): string | null {
  const open = graph.elements.filter((e) => STEPS.has(e.kind) && e.review_status === "draft");
  return (open.find((e) => e.needs_check) ?? open[0] ?? null)?.id ?? null;
}

/**
 * Auto-advance (PRD §5.7.5): after a step is confirmed or rejected, the next unreviewed step:
 * one the verifier only partly supported first, then the next in process order after the step
 * just reviewed (wrapping round). Null when none is left.
 */
export function nextToReview(graph: Graph, afterId: string): string | null {
  const steps = graph.elements.filter((e) => STEPS.has(e.kind));
  const at = steps.findIndex((e) => e.id === afterId);
  const ordered = [...steps.slice(at + 1), ...steps.slice(0, Math.max(at, 0))];
  const open = ordered.filter((e) => e.id !== afterId && e.review_status === "draft");
  return (open.find((e) => e.needs_check) ?? open[0] ?? null)?.id ?? null;
}

/** Steps nobody has reviewed yet. */
export function openSteps(graph: Graph): number {
  return graph.elements.filter((e) => STEPS.has(e.kind) && e.review_status === "draft").length;
}
