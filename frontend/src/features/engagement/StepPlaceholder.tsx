import { Link, useParams } from "react-router";
import { EmptyState, Skeleton } from "../../components/common";
import { useEngagement } from "../../hooks/useEngagements";
import { engagementPath, stepBySlug } from "../../lib/engagementSteps";
import { NotFoundScreen } from "../shell/NotFoundScreen";
import { EngagementProblem } from "./EngagementProblem";

/** Engagement screens that later build phases add: says which phase, and links back to Setup. */
export function StepPlaceholder() {
  const { engagementId = "", step: slug } = useParams();
  const step = stepBySlug(slug);
  const engagement = useEngagement(engagementId);
  if (!step) return <NotFoundScreen />;
  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }
  return (
    <main className="screen" aria-labelledby="step-title">
      <h1 id="step-title">{step.label}</h1>
      {engagement.isPending ? (
        <Skeleton height="80px" />
      ) : (
        <EmptyState
          message={`The ${step.label} screen arrives in build phase ${step.arrives ?? "later"}. Until then, set up the engagement and add its sources.`}
          action={<Link to={engagementPath(engagementId, "setup")}>Go to Setup</Link>}
        />
      )}
    </main>
  );
}
