import { Link, useParams } from "react-router";
import { EmptyState, ErrorState, Skeleton } from "../../components/common";
import { VersionBanner } from "../../components/shell";
import { useDraft } from "../../hooks/useDraft";
import { useEngagement } from "../../hooks/useEngagements";
import { useVersions } from "../../hooks/useVersions";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { EngagementProblem } from "../engagement/EngagementProblem";
import { PublishControls } from "./PublishControls";
import { Workbench } from "./Workbench";
import "./review.css";

const STEPS = new Set(["activity", "decision", "approval"]);

/** Review (PRD §5.6): the current draft in the workbench, with its banner, quality card and Publish. */
export function ReviewScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const draft = useDraft(engagementId);
  const versions = useVersions(engagementId);
  const versionId = draft.data?.version?.id ?? null;

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }
  if (draft.isError) {
    return (
      <main className="screen" aria-labelledby="review-title">
        <h1 id="review-title">Review</h1>
        <ErrorState
          title="The map couldn't be loaded"
          message={messageOf(draft.error)}
          details={copyDetailsOf(draft.error)}
          onRetry={() => void draft.refetch()}
        />
      </main>
    );
  }
  if (draft.isSuccess && !versionId) {
    const running = draft.data.job?.status === "queued" || draft.data.job?.status === "running";
    const published = versions.data?.find((v) => v.state === "published");
    return (
      <main className="screen" aria-labelledby="review-title">
        <h1 id="review-title">Review</h1>
        {published && !running ? (
          <EmptyState
            message={`Nothing to review: ${published.label} is published. To change it, reopen it as a new draft on the Published screen.`}
            action={<Link to={engagementPath(engagementId, "published")}>Go to Published</Link>}
          />
        ) : (
          <EmptyState
            message={
              running
                ? "A draft map is being made. It appears here as soon as it's ready."
                : "There is no draft map to review yet. Create one on the Draft screen."
            }
            action={<Link to={engagementPath(engagementId, "draft")}>Go to Draft</Link>}
          />
        )}
      </main>
    );
  }
  if (!versionId) {
    return (
      <main className="screen" aria-labelledby="review-title" aria-busy="true">
        <h1 id="review-title">Review</h1>
        <Skeleton height="48px" />
        <Skeleton height="96px" />
        <Skeleton height="420px" />
      </main>
    );
  }
  return (
    <Workbench
      engagementId={engagementId}
      versionId={versionId}
      title="Review"
      banner={(g, selectedId, select) => {
        const steps = g.elements.filter((e) => STEPS.has(e.kind));
        const sources = new Set(g.elements.flatMap((e) => e.evidence.map((ev) => ev.source_id))).size;
        return (
          <VersionBanner
            label={g.version.label}
            handoff={
              g.process.engagement_key
                ? { key: g.process.engagement_key, pilot: g.process.pilot_ref ?? "" }
                : undefined
            }
            sources={sources}
            steps={steps}
            selectedId={selectedId}
            onSelect={select}
            signal={versions.data?.find((v) => v.id === g.version.id)?.signal}
            actions={
              g.version.state === "draft" ? (
                <PublishControls versionId={g.version.id} engagementId={engagementId} onSelect={(id) => select(id)} />
              ) : undefined
            }
          />
        );
      }}
    />
  );
}
