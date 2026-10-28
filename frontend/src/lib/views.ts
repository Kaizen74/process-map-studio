// The two views of one map (PRD §3.12.11): As done (default) shows the work as performed, As
// documented the documents' version. The backend lays out each view; the UI only picks which
// one to draw. Pure helpers.

import { plural } from "./format";
import type { GraphElement } from "./mapTypes";

export type AsView = "done" | "documented";

export const AS_VIEWS: readonly { value: AsView; label: string }[] = [
  { value: "done", label: "As done" },
  { value: "documented", label: "As documented" },
];

/** The view a URL asks for (`?as=documented` or `?as=done`); the map's default otherwise. */
export function asView(value: string | null, fallback: AsView = "done"): AsView {
  return value === "documented" || value === "done" ? value : fallback;
}

/** How many steps (not start or end) each view draws. */
export function viewCounts(elements: readonly Pick<GraphElement, "kind" | "view_membership">[]): Record<AsView, number> {
  const steps = elements.filter((e) => e.kind !== "start" && e.kind !== "end");
  return {
    done: steps.filter((e) => inView(e, "done")).length,
    documented: steps.filter((e) => inView(e, "documented")).length,
  };
}

/**
 * The view a map opens in: the one that draws more of it, As done on a tie (§3.12.11). A map from
 * documents alone has nothing As done (2026-10-20); a map mostly from documents shows more As
 * documented (2026-10-28, Eric's cargo manual: 1 step As done, 15 As documented).
 */
export function defaultView(elements: readonly Pick<GraphElement, "kind" | "view_membership">[]): AsView {
  const counts = viewCounts(elements);
  return counts.documented > counts.done ? "documented" : "done";
}

/** Why a map opened As documented (shown while it is). */
export function documentedNote(elements: readonly Pick<GraphElement, "kind" | "view_membership">[]): string {
  const { done, documented } = viewCounts(elements);
  if (done === 0) return DOCUMENTED_DEFAULT_NOTE;
  return `As documented shows more of this map: ${plural(documented, "step")}, against ${done} As done. Showing As documented.`;
}

/** Why a documents-only map opened As documented. */
export const DOCUMENTED_DEFAULT_NOTE =
  "No interview or system record describes these steps yet, so As done has none. Showing As documented.";

/** Whether the step is drawn in a view (steps drafted before v1.10 have no membership: both). */
export function inView(element: Pick<GraphElement, "view_membership">, view: AsView): boolean {
  const membership = element.view_membership ?? "both";
  return membership === "both" || membership === `${view}_only`;
}

/** What a ghosted step says about itself (PRD §3.12.11 "Show the other view"). */
export function ghostLabel(view: AsView): string {
  return view === "done" ? "only in the documented version" : "only in practice";
}

/** A step's value in the active view where the views differ (owner, threshold, time, trigger). */
export function variantFor(element: Pick<GraphElement, "variants">, view: AsView): Record<string, string> {
  return element.variants?.[view] ?? {};
}
