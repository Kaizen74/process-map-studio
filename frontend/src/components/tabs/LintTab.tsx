import type { LintIssue, LintReport } from "../../lib/reviewTypes";

export interface LintTabProps {
  report: LintReport;
  onGoTo: (elementId: string) => void;
}

function Rows({ issues, kind, onGoTo }: { issues: readonly LintIssue[]; kind: string; onGoTo: (id: string) => void }) {
  return (
    <ul className="lint">
      {issues.map((issue, i) => (
        <li key={`${issue.rule}-${i}`} className={`lint__row lint__row--${kind}`}>
          <span className="mono lint__rule">{issue.rule}</span>
          <span className="lint__message">{issue.message}</span>
          {issue.element_id && (
            <button type="button" className="btn btn--link" onClick={() => issue.element_id && onGoTo(issue.element_id)}>
              Go to step
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Map checks (PRD §5.7.10 Lint, §3.7): failures, which block publishing, then warnings. */
export function LintTab({ report, onGoTo }: LintTabProps) {
  const { failures, warnings } = report;
  if (failures.length === 0 && warnings.length === 0) {
    return <p className="tab-empty">Every map check passes: labelled exits, lanes, no orphan steps.</p>;
  }
  return (
    <div className="tab-stack">
      {failures.length > 0 && (
        <section aria-label="Must fix">
          <h3 className="tab-group__title">Must fix before publishing ({failures.length})</h3>
          <Rows issues={failures} kind="failure" onGoTo={onGoTo} />
        </section>
      )}
      {warnings.length > 0 && (
        <section aria-label="Worth a look">
          <h3 className="tab-group__title">Worth a look ({warnings.length})</h3>
          <Rows issues={warnings} kind="warning" onGoTo={onGoTo} />
        </section>
      )}
    </div>
  );
}
