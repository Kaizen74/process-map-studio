// The publish quality card (PRD §5.7.9, §7.2): counts and the "Publish blocked" list. Pure.

import type { PublishBlocker, QualityCard } from "./reviewTypes";

/** "n of 9 green": the hard checks that pass (Q10 is only a warning). */
export function greenCount(card: QualityCard): { green: number; total: number } {
  const hard = card.checks.filter((c) => c.hard);
  return { green: hard.filter((c) => c.status === "pass").length, total: hard.length };
}

/** The blockers of a `409 PUBLISH_BLOCKED` refusal, or null for any other error. */
export function blockersOf(error: unknown): PublishBlocker[] | null {
  if (!error || typeof error !== "object" || !("code" in error) || error.code !== "PUBLISH_BLOCKED") return null;
  const details = "details" in error ? (error.details as { blockers?: unknown }) : {};
  return Array.isArray(details.blockers) ? (details.blockers as PublishBlocker[]) : [];
}
