import { Link } from "react-router";
import { EmptyState, ErrorState } from "../../components/common";
import { copyDetailsOf, isNotFound, messageOf } from "../../lib/errors";

/** An engagement screen that couldn't load: gone (deleted) or another problem. */
export function EngagementProblem({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const gone = isNotFound(error);
  return (
    <main className="screen" aria-labelledby="engagement-problem-title">
      <h1 id="engagement-problem-title">{gone ? "Engagement not found" : "Something went wrong"}</h1>
      {gone ? (
        <EmptyState
          message="That engagement doesn't exist. It may have been deleted."
          action={<Link to="/">Go to Engagements</Link>}
        />
      ) : (
        <ErrorState
          title="This engagement couldn't be opened"
          message={messageOf(error)}
          details={copyDetailsOf(error)}
          onRetry={onRetry}
        />
      )}
    </main>
  );
}
