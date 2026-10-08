import { ErrorState, Skeleton } from "../../components/common";
import { ActivityTable, CaseSummary, RoleTable, TransitionTable, VariantTable } from "../../components/system";
import { useMetrics } from "../../hooks/useSystemRecords";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import type {
  ActivityMetrics,
  CaseMetrics,
  EventLog,
  RoleMetrics,
  TransitionMetrics,
  VariantMetrics,
} from "../../lib/systemRecords";

/** The Metrics tab of an imported log (PRD §5.4): figures per step and role, never per person. */
export function LogFigures({ log }: { log: EventLog }) {
  const cases = useMetrics<CaseMetrics>(log.id, "case");
  const activities = useMetrics<ActivityMetrics>(log.id, "activity");
  const transitions = useMetrics<TransitionMetrics>(log.id, "transition");
  const variants = useMetrics<VariantMetrics>(log.id, "variant");
  const roles = useMetrics<RoleMetrics>(log.id, "role");
  const all = [cases, activities, transitions, variants, roles];

  const failed = all.find((q) => q.isError);
  if (failed) {
    return (
      <ErrorState
        title="The figures couldn't be loaded"
        message={messageOf(failed.error)}
        details={copyDetailsOf(failed.error)}
        onRetry={() => all.forEach((q) => void q.refetch())}
      />
    );
  }
  return (
    <div className="log-metrics">
      <p className="system-matching__intro">
        Worked out once when the log was imported. Figures are per activity and role only, and anything resting on fewer
        than 5 cases is left out. Times are median and 90th percentile.
      </p>
      {cases.data ? <CaseSummary data={cases.data} /> : <Skeleton height="120px" />}
      {activities.data ? <ActivityTable data={activities.data} /> : <Skeleton height="120px" />}
      {transitions.data ? <TransitionTable data={transitions.data} /> : <Skeleton height="120px" />}
      {variants.data ? <VariantTable data={variants.data} /> : <Skeleton height="120px" />}
      {roles.data ? <RoleTable data={roles.data} /> : <Skeleton height="120px" />}
    </div>
  );
}
