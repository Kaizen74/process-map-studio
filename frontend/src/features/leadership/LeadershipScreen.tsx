import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { EmptyState, ErrorState, SelectField, Skeleton } from "../../components/common";
import { FactsColumn, InterpretationColumn, RecommendationColumn } from "../../components/leadership";
import { useToast } from "../../components/shell";
import { useEngagement } from "../../hooks/useEngagements";
import { useLeadership, useSaveDecisions } from "../../hooks/useLeadership";
import { useGraph } from "../../hooks/useReview";
import { useVersions } from "../../hooks/useVersions";
import { stepPath } from "../../lib/currentMap";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { formatDate } from "../../lib/format";
import type { VersionSummary } from "../../lib/reviewTypes";
import { EngagementProblem } from "../engagement/EngagementProblem";

/**
 * Leadership (PRD §5.4): where the process jams and why, for a published map, in three columns
 * kept apart: Facts, Interpretation, Recommendation. Every figure opens the steps behind it.
 */
export function LeadershipScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const versions = useVersions(engagementId);
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();

  const published = (versions.data ?? []).filter((v) => v.state === "published" || v.state === "superseded");
  const chosen: VersionSummary | undefined =
    published.find((v) => v.id === params.get("version")) ??
    published.find((v) => v.state === "published") ??
    published[0];
  const view = useLeadership(chosen?.id ?? null);
  const graph = useGraph(chosen?.id ?? null);
  const save = useSaveDecisions(chosen?.id ?? "");

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }

  const labels = new Map((graph.data?.elements ?? []).map((e) => [e.id, e.label]));
  const open = (elementId: string) => {
    if (chosen) void navigate(stepPath(engagementPath(engagementId), chosen, elementId));
  };
  const failed = versions.isError ? versions.error : view.isError ? view.error : null;

  return (
    <main className="screen" aria-labelledby="leadership-title">
      <div>
        <h1 id="leadership-title">Leadership</h1>
        <p className="screen__intro">
          Where the process jams and why, from the published map. Facts, interpretation and recommendation are kept
          apart; open any figure to see the steps behind it.
        </p>
      </div>
      {(versions.isPending || (chosen && view.isPending)) && <Skeleton height="240px" />}
      {failed && (
        <ErrorState
          title="The leadership view couldn't be loaded"
          message={messageOf(failed)}
          details={copyDetailsOf(failed)}
          onRetry={() => void (versions.isError ? versions.refetch() : view.refetch())}
        />
      )}
      {versions.isSuccess && !chosen && (
        <EmptyState
          message="Publish a version first. The leadership view shows a map you have reviewed and published, not a draft."
          action={<Link to={engagementPath(engagementId, "review")}>Go to Review</Link>}
        />
      )}
      {chosen && published.length > 1 && (
        <div className="leadership__version">
          <SelectField
            label="Version"
            value={chosen.id}
            options={published.map((v) => ({
              value: v.id,
              label: `${v.label} · ${v.state === "superseded" ? "superseded" : "published"} ${formatDate(v.published_at ?? "")}`,
            }))}
            onChange={(id) =>
              setParams(
                (current) => {
                  const next = new URLSearchParams(current);
                  next.set("version", id);
                  return next;
                },
                { replace: true },
              )
            }
          />
        </div>
      )}
      {view.data && (
        <div className="leadership-columns">
          <FactsColumn view={view.data} labels={labels} onOpen={open} />
          <InterpretationColumn view={view.data} labels={labels} onOpen={open} />
          <RecommendationColumn
            key={view.data.version.id}
            view={view.data}
            labels={labels}
            saving={save.isPending}
            problem={save.error ? messageOf(save.error) : null}
            onOpen={open}
            onSave={(lines) => save.mutate(lines, { onSuccess: () => toast("Decisions saved.") })}
          />
        </div>
      )}
    </main>
  );
}
