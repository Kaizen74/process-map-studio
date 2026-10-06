import { useState } from "react";
import { CHOOSABLE_WORK_TYPES, type ChoosableWorkType, type WorkType } from "../../lib/mapTypes";
import { WORK_TYPE_LABELS } from "../../lib/lens";
import { Button, SelectField } from "../common";

// Confirm or change a step's work type (PRD §5.7.7 4a, criterion 54; V3b). Presentational: the
// screen saves the choice. Complex or chaotic work is never an automation candidate, so the help
// line says what choosing it does to an automation flag.

export interface WorkTypeChoiceProps {
  type: WorkType;
  confirmed: boolean;
  busy: boolean;
  /** A refusal from the server, in plain words. */
  error?: string | null | undefined;
  onSave: (type: ChoosableWorkType) => void;
}

export function WorkTypeChoice({ type, confirmed, busy, error, onSave }: WorkTypeChoiceProps) {
  const [changing, setChanging] = useState(false);
  const classified = type !== "not_classified";
  const [choice, setChoice] = useState<ChoosableWorkType>(classified ? type : "complicated");
  if (changing) {
    return (
      <form
        className="stack work-type-choice"
        onSubmit={(event) => {
          event.preventDefault();
          onSave(choice);
          setChanging(false);
        }}
      >
        <SelectField
          label="Work type"
          value={choice}
          options={CHOOSABLE_WORK_TYPES.map((value) => ({ value, label: WORK_TYPE_LABELS[value] }))}
          onChange={(value) => setChoice(value as ChoosableWorkType)}
          help="Complex or chaotic work is a judgment step and never an automation candidate."
        />
        <div className="work-type-choice__actions">
          <Button type="submit" variant="primary" disabled={busy}>
            Save work type
          </Button>
          <Button onClick={() => setChanging(false)}>Cancel</Button>
        </div>
      </form>
    );
  }
  return (
    <div className="stack work-type-choice">
      {confirmed && <p className="sense-note">You confirmed this work type.</p>}
      <div className="work-type-choice__actions">
        {classified && !confirmed && (
          <Button variant="primary" disabled={busy} onClick={() => onSave(type)}>
            Confirm work type
          </Button>
        )}
        <Button disabled={busy} onClick={() => setChanging(true)}>
          {classified ? "Change work type" : "Choose work type"}
        </Button>
      </div>
      {error && (
        <p className="panel-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
