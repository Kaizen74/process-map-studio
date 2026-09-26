import { Navigate, useParams } from "react-router";
import { Skeleton } from "../../components/common";
import { useReadiness } from "../../hooks/useEngagements";
import { engagementPath } from "../../lib/engagementSteps";
import { EngagementProblem } from "./EngagementProblem";

/** Opening an engagement goes to its next recommended screen (PRD §5.4 Home, card click). */
export function EngagementIndex() {
  const { engagementId = "" } = useParams();
  const readiness = useReadiness(engagementId);
  if (readiness.isError) return <EngagementProblem error={readiness.error} onRetry={() => void readiness.refetch()} />;
  if (readiness.data) {
    return <Navigate to={engagementPath(engagementId, readiness.data.next_step ?? "published")} replace />;
  }
  return (
    <main className="screen" aria-busy="true" aria-label="Opening the engagement">
      <Skeleton height="24px" width="30%" />
      <Skeleton height="120px" />
    </main>
  );
}
