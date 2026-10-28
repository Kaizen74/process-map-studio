import { useParams } from "react-router";
import { Card, ErrorState, Skeleton } from "../../components/common";
import { useEngagement } from "../../hooks/useEngagements";
import { useRoles } from "../../hooks/useRoles";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { EngagementProblem } from "../engagement/EngagementProblem";
import { AnotherFlowCard } from "./AnotherFlowCard";
import { RolesCard } from "./RolesCard";
import { ConventionsCard } from "./ConventionsCard";
import { ScopeCard } from "./ScopeCard";
import "./setup.css";

/** Setup (PRD §5.4): mapping conventions, process scope, roles and lanes, and another flow. */
export function SetupScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const roles = useRoles(engagementId);

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }
  return (
    <main className="screen" aria-labelledby="setup-title">
      <div>
        <h1 id="setup-title">Setup</h1>
        <p className="screen__intro">Describe the process and the roles involved. You can change these at any time.</p>
      </div>
      <div className="setup-grid">
        {engagement.data && <ConventionsCard key={`conventions-${engagement.data.id}`} engagement={engagement.data} />}
        {engagement.data ? (
          <ScopeCard key={engagement.data.id} engagement={engagement.data} />
        ) : (
          <Card title="Process scope">
            <div className="stack" aria-busy="true">
              <Skeleton height="28px" />
              <Skeleton height="28px" />
              <Skeleton height="28px" width="70%" />
            </div>
          </Card>
        )}
        {roles.isError ? (
          <ErrorState
            title="The roles couldn't be loaded"
            message={messageOf(roles.error)}
            details={copyDetailsOf(roles.error)}
            onRetry={() => void roles.refetch()}
          />
        ) : roles.data ? (
          <RolesCard engagementId={engagementId} roles={roles.data} />
        ) : (
          <Card title="Roles and lanes">
            <div className="stack" aria-busy="true">
              <Skeleton height="28px" />
              <Skeleton height="28px" />
            </div>
          </Card>
        )}
        {engagement.data && <AnotherFlowCard engagement={engagement.data} />}
      </div>
    </main>
  );
}
