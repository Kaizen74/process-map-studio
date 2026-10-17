import { Button } from "../common";
import { plural } from "../../lib/format";
import { basisText, shortDuration, type CaseKeyMap } from "../../lib/systemRecords";
import "./system.css";

export interface CaseKeyMapListProps {
  maps: readonly CaseKeyMap[];
  busy: boolean;
  onRemove: (map: CaseKeyMap) => void;
}

/** What one link found, in words: how many pairs each log knows. */
function foundText(map: CaseKeyMap): string {
  return `${plural(map.pairs, "pair")} in the file: ${map.from_found} found in ${map.from_log_name}, ${map.to_found} in ${map.to_log_name}, ${plural(map.linked_cases, "case")} in both.`;
}

/**
 * Linked logs (R11c): each case-key map with the end-to-end time across both systems, measured,
 * or why there is none. Presentational: the backend counts and works out every figure.
 */
export function CaseKeyMapList({ maps, busy, onRemove }: CaseKeyMapListProps) {
  if (maps.length === 0) {
    return <p className="log-metrics__muted">No logs are linked yet. Each log is analysed on its own.</p>;
  }
  return (
    <ul className="case-key-list" aria-label="Linked logs">
      {maps.map((map) => (
        <li key={`${map.from_log_id}>${map.to_log_id}`} className="case-key-list__row">
          <p className="log-list__name">
            {map.from_log_name} and {map.to_log_name}
          </p>
          <p className="log-list__meta">{foundText(map)}</p>
          {map.end_to_end ? (
            <p>
              End to end across both systems: median {shortDuration(map.end_to_end.median_min)}, 90th percentile{" "}
              {shortDuration(map.end_to_end.p90_min)} ({plural(map.end_to_end.n, "case")}, measured;{" "}
              {basisText(map.basis).toLowerCase()}).
            </p>
          ) : (
            <p className="log-metrics__muted">
              Too few linked cases to show a time: fewer than {map.minimum_cases}.
            </p>
          )}
          <Button variant="link" disabled={busy} onClick={() => onRemove(map)}>
            Unlink {map.from_log_name} and {map.to_log_name}
          </Button>
        </li>
      ))}
    </ul>
  );
}
