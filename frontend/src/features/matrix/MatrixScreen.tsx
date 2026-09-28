import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { EmptyState, ErrorState, SegmentedControl, Skeleton } from "../../components/common";
import { AlignmentTable } from "../../components/matrix";
import { useEngagement } from "../../hooks/useEngagements";
import { useAlignmentMatrix, useVersions } from "../../hooks/useVersions";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import {
  DIVERGENCE_TYPES,
  divergenceCounts,
  filterRows,
  sortRows,
  type MatrixSort,
} from "../../lib/matrix";
import { EngagementProblem } from "../engagement/EngagementProblem";

const SORTS = [
  { value: "process", label: "Process order" },
  { value: "severity", label: "Most serious first" },
] as const;

/**
 * Matrix (PRD §5.4): how each kind of source stands on each step of the map Eric is working on
 * (the draft, else the latest published version). Filter by divergence type, sort by severity;
 * a row opens its step on Review (or Published).
 */
export function MatrixScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const versions = useVersions(engagementId);
  const navigate = useNavigate();
  const [types, setTypes] = useState<ReadonlySet<string>>(new Set());
  const [sort, setSort] = useState<MatrixSort>("process");

  const list = versions.data ?? [];
  const current = list.find((v) => v.state === "draft") ?? list.find((v) => v.state === "published") ?? null;
  const matrix = useAlignmentMatrix(current?.id ?? null);

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }

  function open(elementId: string) {
    if (!current) return;
    const step = encodeURIComponent(elementId);
    void navigate(
      current.state === "draft"
        ? `${engagementPath(engagementId, "review")}?step=${step}`
        : `${engagementPath(engagementId, "published")}?version=${encodeURIComponent(current.id)}&step=${step}`,
    );
  }

  function toggle(type: string) {
    const next = new Set(types);
    if (next.has(type)) next.delete(type);
    else next.add(type);
    setTypes(next);
  }

  const rows = matrix.data ?? [];
  const counts = divergenceCounts(rows);
  const shown = sortRows(filterRows(rows, types), sort);
  const loading = versions.isPending || (current !== null && matrix.isPending);
  const failed = versions.isError ? versions.error : matrix.isError ? matrix.error : null;

  return (
    <main className="screen" aria-labelledby="matrix-title">
      <div>
        <h1 id="matrix-title">Matrix</h1>
        <p className="screen__intro">
          How each kind of source stands on each step
          {current ? ` of ${current.label}${current.state === "draft" ? "" : " (published)"}` : ""}. Sources are
          compared, never merged: a source that doesn't mention a step is silent, which is not a contradiction.
        </p>
      </div>
      {loading && <Skeleton height="240px" />}
      {failed !== null && (
        <ErrorState
          title="The matrix couldn't be loaded"
          message={messageOf(failed)}
          details={copyDetailsOf(failed)}
          onRetry={() => {
            void versions.refetch();
            void matrix.refetch();
          }}
        />
      )}
      {!versions.isPending && !versions.isError && current === null && (
        <EmptyState
          message="No draft map yet. Create one on Draft; the matrix then compares every source with every step."
          action={<Link to={engagementPath(engagementId, "draft")}>Go to Draft</Link>}
        />
      )}
      {matrix.isSuccess && (
        <>
          <div className="matrix-toolbar">
            <fieldset className="matrix-filters">
              <legend>Divergence</legend>
              {DIVERGENCE_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  className="chip matrix-filter"
                  aria-pressed={types.has(t.value)}
                  onClick={() => toggle(t.value)}
                >
                  {t.label} <span className="mono">{counts.get(t.value) ?? 0}</span>
                </button>
              ))}
            </fieldset>
            <SegmentedControl label="Sort" options={SORTS} value={sort} onChange={setSort} />
          </div>
          <p className="inline-note" aria-live="polite">
            {types.size === 0
              ? `${rows.length} ${rows.length === 1 ? "step" : "steps"}.`
              : `${shown.length} of ${rows.length} steps have the chosen divergence.`}
          </p>
          {shown.length > 0 ? (
            <AlignmentTable rows={shown} onOpen={open} />
          ) : (
            <p className="inline-note">
              {rows.length === 0
                ? "The map has no steps yet."
                : "No step has the chosen divergence. Choose another type, or clear the choice."}
            </p>
          )}
        </>
      )}
    </main>
  );
}
