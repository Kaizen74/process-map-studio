import { Button, Chip } from "../common";
import { formatDate, plural } from "../../lib/format";
import { LOG_STATUS_LABELS, type EventLog } from "../../lib/systemRecords";
import "./system.css";

export interface LogListProps {
  logs: readonly EventLog[];
  /** The log open in the wizard or detail, if any. */
  openId?: string | null;
  onOpen: (logId: string) => void;
  onDelete: (log: EventLog) => void;
}

function windowText(log: EventLog): string {
  if (log.window_start && log.window_end) return `${formatDate(log.window_start)} to ${formatDate(log.window_end)}`;
  return "No date window given";
}

/** The engagement's logs with status, window, cases and events (PRD §5.4 System records). */
export function LogList({ logs, openId, onOpen, onDelete }: LogListProps) {
  return (
    <ul className="log-list">
      {logs.map((log) => {
        const report = log.validation_report;
        const imported = log.status === "imported";
        return (
          <li key={log.id} className={`log-list__row${log.id === openId ? " log-list__row--open" : ""}`}>
            <div className="log-list__main">
              <p className="log-list__name">
                {log.name}
                {log.system && <span className="log-list__system"> · {log.system}</span>}
              </p>
              <p className="log-list__meta">
                <Chip tone={imported ? "good" : log.status === "failed" ? "danger" : "neutral"}>
                  {LOG_STATUS_LABELS[log.status]}
                </Chip>{" "}
                {windowText(log)}
                {imported && report && ` · ${plural(report.cases, "case")} · ${plural(report.rows_kept, "event")}`}
              </p>
            </div>
            <div className="log-list__actions">
              {log.status !== "failed" && (
                <Button onClick={() => onOpen(log.id)} aria-current={log.id === openId || undefined}>
                  {imported ? `Open ${log.name}` : `Continue ${log.name}`}
                </Button>
              )}
              <Button variant="link" onClick={() => onDelete(log)}>
                Delete {log.name}
              </Button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
