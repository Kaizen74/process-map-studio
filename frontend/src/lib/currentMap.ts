// The map Eric is working on (API_CONTRACT.md → coverage): the draft, else the latest published
// version. Shared by the Matrix and Registers screens.
import type { VersionSummary } from "./reviewTypes";

export function currentMap(versions: readonly VersionSummary[]): VersionSummary | null {
  return versions.find((v) => v.state === "draft") ?? versions.find((v) => v.state === "published") ?? null;
}

/** Where a step of that map opens: Review for a draft, Published for a published version. */
export function stepPath(engagementPath: string, map: VersionSummary, elementId: string): string {
  const step = encodeURIComponent(elementId);
  return map.state === "draft"
    ? `${engagementPath}/review?step=${step}`
    : `${engagementPath}/published?version=${encodeURIComponent(map.id)}&step=${step}`;
}
