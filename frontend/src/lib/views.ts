// The two views of one map (PRD §3.12.11): As done (default) shows the work as performed, As
// documented the documents' version. The backend lays out each view; the UI only picks which
// one to draw. Pure helpers.

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

/**
 * The view a map opens in: As done, unless no step is in it but some are As documented. A map
 * drafted from documents alone (Eric, 2026-10-20) has no lived or traced step to draw As done.
 */
export function defaultView(elements: readonly Pick<GraphElement, "kind" | "view_membership">[]): AsView {
  const steps = elements.filter((e) => e.kind !== "start" && e.kind !== "end");
  const documentedOnly = steps.length > 0 && !steps.some((e) => inView(e, "done"));
  return documentedOnly ? "documented" : "done";
}

/** Why a map opened As documented (shown while it is). */
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
