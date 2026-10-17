import { useState } from "react";
import { Button, Chip, SelectField } from "../common";
import { plural } from "../../lib/format";
import {
  ALIGNMENT_STATUS_LABELS,
  PROPOSED_BY_LABELS,
  type Alignment,
  type AlignmentDecision,
  type AlignmentRow,
} from "../../lib/systemRecords";
import "./system.css";

export interface LogAlignmentTableProps {
  alignment: Alignment;
  /** The current map's steps, in map order, for "Choose another step". */
  steps: readonly { id: string; label: string }[];
  onDecide: (decision: AlignmentDecision) => void;
}

function StatusChip({ row }: { row: AlignmentRow }) {
  if (!row.confirmed) {
    return (
      <Chip dashed title="Waiting for your decision">
        {ALIGNMENT_STATUS_LABELS[row.status === "confirmed" ? "proposed" : row.status]}: waiting
      </Chip>
    );
  }
  return <Chip tone={row.status === "confirmed" ? "good" : "neutral"}>{ALIGNMENT_STATUS_LABELS[row.status]}</Chip>;
}

function ActivityActions({ row, steps, onDecide }: { row: AlignmentRow; steps: LogAlignmentTableProps["steps"]; onDecide: LogAlignmentTableProps["onDecide"] }) {
  const [choosing, setChoosing] = useState(false);
  const [stepId, setStepId] = useState(row.element_id ?? steps[0]?.id ?? "");
  const match = (id: string) => onDecide({ activity: row.activity, element_id: id, status: "confirmed" });
  if (choosing) {
    return (
      <div className="log-align__choose">
        <SelectField
          label={`Step for ${row.activity}`}
          value={stepId}
          options={steps.map((s) => ({ value: s.id, label: s.label }))}
          onChange={setStepId}
        />
        <div className="log-align__buttons">
          <Button
            variant="primary"
            onClick={() => {
              setChoosing(false);
              match(stepId);
            }}
          >
            Match to this step
          </Button>
          <Button variant="link" onClick={() => setChoosing(false)}>
            Cancel
          </Button>
        </div>
      </div>
    );
  }
  const unconfirmedMatch = !row.confirmed && row.element_id !== null;
  const unconfirmedHidden = !row.confirmed && row.status === "hidden_work";
  return (
    <div className="log-align__buttons">
      {unconfirmedMatch && row.element_id && (
        <Button variant="primary" aria-label={`Confirm ${row.activity} as ${row.element_label}`} onClick={() => match(row.element_id ?? "")}>
          Confirm
        </Button>
      )}
      {unconfirmedHidden && (
        <Button
          variant="primary"
          aria-label={`Confirm ${row.activity} as hidden work`}
          onClick={() => onDecide({ activity: row.activity, element_id: null, status: "hidden_work" })}
        >
          Confirm hidden work
        </Button>
      )}
      <Button aria-label={`Choose another step for ${row.activity}`} onClick={() => setChoosing(true)}>
        Choose another step
      </Button>
      {!(row.status === "hidden_work") && (
        <Button
          variant="link"
          aria-label={`Mark ${row.activity} as hidden work`}
          onClick={() => onDecide({ activity: row.activity, element_id: null, status: "hidden_work" })}
        >
          Hidden work
        </Button>
      )}
    </div>
  );
}

/**
 * The alignment table (PRD §5.4 System records, §3.13.4): each system activity with its suggested
 * step, the reason and its status, and Eric's decision (Confirm · Choose another step · Hidden
 * work); the steps no activity is matched to are listed below. Nothing counts until confirmed.
 */
export function LogAlignmentTable({ alignment, steps, onDecide }: LogAlignmentTableProps) {
  const activities = alignment.rows.filter((r) => r.activity);
  const unrecorded = alignment.rows.filter((r) => !r.activity);
  const s = alignment.summary;
  return (
    <div className="log-align">
      <p className="log-align__summary" role="status">
        {plural(s.activities, "activity", "activities")}: {s.matched} matched, {s.hidden_work} hidden work.{" "}
        {plural(s.no_system_record, "step")} with no system record.{" "}
        {s.waiting > 0 ? `${s.waiting} waiting for your decision.` : "Everything is decided."}
      </p>
      <table className="log-align__table">
        <caption className="log-align__caption">System activities</caption>
        <thead>
          <tr>
            <th scope="col">Activity</th>
            <th scope="col">Cases</th>
            <th scope="col">Step on the map</th>
            <th scope="col">Status and why</th>
            <th scope="col">Your decision</th>
          </tr>
        </thead>
        <tbody>
          {activities.map((row) => (
            <tr key={row.activity}>
              <th scope="row">{row.activity}</th>
              <td>
                {row.cases}
                <span className="log-align__muted"> ({plural(row.events, "event")})</span>
              </td>
              <td>{row.element_label || <span className="log-align__muted">No step</span>}</td>
              <td>
                <StatusChip row={row} />
                <p className="log-align__reason">
                  {row.confirmed ? PROPOSED_BY_LABELS.eric : PROPOSED_BY_LABELS[row.proposed_by]}
                  {row.reason && `. ${row.reason}`}
                </p>
              </td>
              <td>
                <ActivityActions key={`${row.element_id ?? ""}-${row.status}`} row={row} steps={steps} onDecide={onDecide} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {unrecorded.length > 0 && (
        <table className="log-align__table">
          <caption className="log-align__caption">Steps with no system record</caption>
          <thead>
            <tr>
              <th scope="col">Step</th>
              <th scope="col">Status</th>
              <th scope="col">Your decision</th>
            </tr>
          </thead>
          <tbody>
            {unrecorded.map((row) => (
              <tr key={row.element_id ?? row.element_label}>
                <th scope="row">{row.element_label}</th>
                <td>
                  <StatusChip row={row} />
                  <p className="log-align__reason">
                    {row.confirmed ? "You confirmed it is done offline or not recorded." : row.reason}
                  </p>
                </td>
                <td>
                  {row.confirmed ? (
                    <span className="log-align__muted">Decided</span>
                  ) : (
                    <Button
                      aria-label={`Confirm ${row.element_label} has no system record`}
                      onClick={() => onDecide({ activity: "", element_id: row.element_id, status: "no_system_record" })}
                    >
                      Confirm no system record
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
