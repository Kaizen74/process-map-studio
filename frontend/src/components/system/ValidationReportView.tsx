import { formatDate, plural } from "../../lib/format";
import type { ValidationReport } from "../../lib/systemRecords";
import "./system.css";

export interface ValidationReportViewProps {
  report: ValidationReport;
  /** The final report after the import, or a preview while mapping. */
  final?: boolean;
}

const pct = (share: number) => `${Math.round(share * 100)}%`;

/** How to fix the extract for the backend's refusal (PRD §5.4: each reason with how to fix it). */
function fixFor(report: ValidationReport): string {
  if (report.missing_columns.length > 0) {
    return "Map the column that holds it, or ask IT for an extract that includes it: the data request template lists the columns.";
  }
  if (report.rows_read === 0) return "Ask IT for the extract again, covering the agreed dates.";
  return "See the dropped rows below: choose the right date format, or ask IT for a cleaner extract.";
}

/** The validation report (§3.13.3 step 4): counts only, never a row, a case or a user ID. */
export function ValidationReportView({ report, final = false }: ValidationReportViewProps) {
  const d = report.dropped;
  const dropped = d.unparseable_time + d.missing_case_or_activity + d.duplicate;
  return (
    <div className="log-report">
      {report.refused ? (
        <div className="log-report__refused" role="alert">
          <p className="log-report__verdict">The import would be refused</p>
          <p>{report.refusal}</p>
          <p>
            <strong>How to fix it:</strong> {fixFor(report)}
          </p>
        </div>
      ) : (
        <p className="log-report__verdict">{final ? "Imported." : "Ready to import."}</p>
      )}
      <dl className="log-report__figures">
        <dt>Rows read</dt>
        <dd>{report.rows_read}</dd>
        <dt>Rows kept</dt>
        <dd>{report.rows_kept}</dd>
        <dt>Cases</dt>
        <dd>{report.cases}</dd>
        <dt>Activities</dt>
        <dd>{report.activities}</dd>
        <dt>Dates</dt>
        <dd>
          {report.date_from && report.date_to
            ? `${formatDate(report.date_from)} to ${formatDate(report.date_to)}`
            : "None readable"}
        </dd>
        <dt>Date format</dt>
        <dd className="mono">{report.timestamp_format || "Not detected"}</dd>
      </dl>
      {dropped > 0 && (
        <>
          <p className="log-report__sub">
            {plural(dropped, "row")} dropped ({pct(report.dropped_share)}):
          </p>
          <ul className="log-report__list">
            {d.unparseable_time > 0 && <li>{plural(d.unparseable_time, "row")} with a date the app couldn't read</li>}
            {d.missing_case_or_activity > 0 && (
              <li>{plural(d.missing_case_or_activity, "row")} without a case ID or activity</li>
            )}
            {d.duplicate > 0 && <li>{plural(d.duplicate, "duplicate row")}</li>}
          </ul>
        </>
      )}
      <ul className="log-report__list">
        {report.single_event_cases > 0 && (
          <li>{plural(report.single_event_cases, "case")} with only one event (kept; they show no waits).</li>
        )}
        {report.outside_window > 0 && (
          <li>{plural(report.outside_window, "event")} outside the agreed date window (kept).</li>
        )}
        {report.unknown_role_events > 0 && (
          <li>
            {plural(report.unknown_role_events, "event")} with an unknown role: their figures show under Unknown role.
          </li>
        )}
      </ul>
    </div>
  );
}
