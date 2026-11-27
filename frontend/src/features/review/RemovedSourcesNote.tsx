import { useVersion } from "../../hooks/useVersions";

/**
 * DECISIONS 114: a draft made from sources that were deleted afterwards says so, until it is
 * refreshed, so a draft that quietly lost its evidence is never mistaken for a current one.
 */
export function RemovedSourcesNote({ versionId }: { versionId: string }) {
  const version = useVersion(versionId);
  const removed = version.data?.removed_sources ?? [];
  if (removed.length === 0) return null;
  const files =
    removed.length === 1
      ? removed[0]
      : `${removed.slice(0, -1).join(", ")} and ${removed[removed.length - 1]}`;
  return (
    <p className="removed-sources" role="status">
      <strong>Needs a refresh.</strong> This draft was made from {files}, which{" "}
      {removed.length === 1 ? "has" : "have"} since been deleted. Steps that
      cited {removed.length === 1 ? "it" : "them"} have lost that evidence.
      Refresh the draft (More, then Refresh draft from sources) to rebuild it
      from the sources you have now.
    </p>
  );
}
