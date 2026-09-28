// The guided engagement path (PRD §5.3): order, labels, addresses and the build phase in which
// each screen arrives. Statuses come from the readiness endpoint; nothing is decided here.
import type { NavKey } from "../api/types";

export interface EngagementStep {
  key: NavKey;
  label: string;
  slug: string;
  optional?: boolean;
  /** Build phase (PRD §6.3) in which the screen arrives; omitted once it is built. */
  arrives?: string;
}

export const ENGAGEMENT_STEPS: readonly EngagementStep[] = [
  { key: "setup", label: "Setup", slug: "setup" },
  { key: "sources", label: "Sources", slug: "sources" },
  { key: "draft", label: "Draft", slug: "draft" },
  { key: "review", label: "Review", slug: "review" },
  { key: "published", label: "Published", slug: "published" },
  { key: "matrix", label: "Matrix", slug: "matrix", arrives: "P9" },
  { key: "gap_analysis", label: "Gap analysis", slug: "gap-analysis", optional: true, arrives: "P10" },
  { key: "registers", label: "Registers", slug: "registers", arrives: "P9" },
  { key: "leadership", label: "Leadership", slug: "leadership", arrives: "P11" },
  { key: "exports", label: "Exports", slug: "exports", arrives: "P7" },
];

export function engagementPath(id: string, key?: NavKey | null): string {
  const base = `/engagements/${encodeURIComponent(id)}`;
  const step = ENGAGEMENT_STEPS.find((s) => s.key === key);
  return step ? `${base}/${step.slug}` : base;
}

export function stepBySlug(slug: string | undefined): EngagementStep | undefined {
  return ENGAGEMENT_STEPS.find((s) => s.slug === slug);
}
