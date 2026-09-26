import { Link } from "react-router";
import { EmptyState } from "../../components/common";

export function NotFoundScreen() {
  return (
    <main className="screen" aria-labelledby="not-found-title">
      <h1 id="not-found-title">Page not found</h1>
      <EmptyState
        message="That page doesn't exist in the app, or isn't built yet."
        action={<Link to="/">Go to Engagements</Link>}
      />
    </main>
  );
}
