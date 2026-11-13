// The guided engagement path (PRD §5.3): order, labels, addresses and the build phase in which
// each screen arrives. Statuses come from the readiness endpoint; nothing is decided here.
import type { NavKey, Settings } from "../api/types";

/** Steps of optional modules (decision A) are not in the readiness endpoint's nav. */
export type StepKey = NavKey | "system_records" | "reality" | "compare";

export interface EngagementStep {
  key: StepKey;
  label: string;
  slug: string;
  optional?: boolean;
  /** The Settings switch an optional module's step needs (shown only while it is on). */
  module?: keyof Pick<
    Settings,
    "system_records_enabled" | "gap_analysis_enabled" | "reality_views_enabled"
  >;
  /** Build phase (PRD §6.3) in which the screen arrives; omitted once it is built. */
  arrives?: string;
  /** Off the main path, under "More" in the bar (2026-10-28, Eric: "not sure what to do when"). */
  more?: boolean;
}

export const ENGAGEMENT_STEPS: readonly EngagementStep[] = [
  { key: "setup", label: "Setup", slug: "setup" },
  { key: "interview", label: "Interview", slug: "interview", more: true },
  { key: "sources", label: "Sources", slug: "sources" },
  {
    key: "system_records",
    label: "System records",
    slug: "system-records",
    optional: true,
    module: "system_records_enabled",
    more: true,
  },
  { key: "draft", label: "Draft", slug: "draft" },
  { key: "review", label: "Review", slug: "review" },
  { key: "published", label: "Published", slug: "published" },
  { key: "matrix", label: "Matrix", slug: "matrix", more: true },
  {
    key: "gap_analysis",
    label: "Gap analysis",
    slug: "gap-analysis",
    optional: true,
    module: "gap_analysis_enabled",
    more: true,
  },
  { key: "registers", label: "Registers", slug: "registers", more: true },
  {
    key: "reality",
    label: "Reality",
    slug: "reality",
    optional: true,
    module: "reality_views_enabled",
    more: true,
  },
  { key: "leadership", label: "Leadership", slug: "leadership", more: true },
  // DECISIONS 98: the same process in another country; optional, needs two published maps.
  { key: "compare", label: "Compare countries", slug: "compare", optional: true, more: true },
  { key: "exports", label: "Exports", slug: "exports" },
];

export function engagementPath(id: string, key?: StepKey | null): string {
  const base = `/engagements/${encodeURIComponent(id)}`;
  const step = ENGAGEMENT_STEPS.find((s) => s.key === key);
  return step ? `${base}/${step.slug}` : base;
}

export function stepBySlug(
  slug: string | undefined,
): EngagementStep | undefined {
  return ENGAGEMENT_STEPS.find((s) => s.slug === slug);
}

/** The steps to show: optional modules only while their Settings switch is on. */
export function visibleSteps(settings: Settings | undefined): EngagementStep[] {
  return ENGAGEMENT_STEPS.filter(
    (s) => !s.module || settings?.[s.module] === true,
  );
}
