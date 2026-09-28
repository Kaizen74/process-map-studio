import { formatDateTime } from "../../lib/format";
import type { AuditEntry } from "../../lib/reviewTypes";

/** The version's audit log (PRD §5.7.10): mono time · action · target, newest first. */
export function AuditTab({ entries }: { entries: readonly AuditEntry[] }) {
  if (entries.length === 0) {
    return <p className="tab-empty">Nothing has changed on this draft yet. Every review action will be listed here.</p>;
  }
  return (
    <table className="audit">
      <caption className="visually-hidden">Audit log, newest first</caption>
      <thead>
        <tr>
          <th scope="col">Time</th>
          <th scope="col">Action</th>
          <th scope="col">Step</th>
          <th scope="col">By</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.id}>
            <td className="mono audit__time">{formatDateTime(entry.at)}</td>
            <td className="audit__action">{entry.action}</td>
            <td>{entry.target_label || "No longer on the map"}</td>
            <td className="audit__actor">{entry.actor}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
