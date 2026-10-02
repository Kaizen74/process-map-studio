// The two views of one map (PRD §3.12.11): As done (default) shows the work as performed, As
// documented the documents' version. The backend lays out each view; the UI only picks which
// one to draw. Pure helpers.

import type { GraphElement } from "./mapTypes";

export type AsView = "done" | "documented";

export const AS_VIEWS: readonly { value: AsView; label: string }[] = [
  { value: "done", label: "As done" },
  { value: "documented", label: "As documented" },
];

/** The view a URL asks for (`?as=documented`); As done otherwise. */
export function asView(value: string | null): AsView {
  return value === "documented" ? "documented" : "done";
}

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
