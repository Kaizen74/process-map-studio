import { SelectField } from "../common";
import { LOG_FIELDS, LOG_FIELD_LABELS, REQUIRED_FIELDS, type LogField } from "../../lib/systemRecords";
import "./system.css";

export interface ColumnMapTableProps {
  /** The file's headers, in file order, each with its chosen field (null: left out). */
  columns: Record<string, string | null>;
  onChange: (header: string, field: string | null) => void;
}

const LEAVE_OUT = "";
const OPTIONS = [
  { value: LEAVE_OUT, label: "Leave out" },
  ...LOG_FIELDS.map((f) => ({ value: f, label: LOG_FIELD_LABELS[f] })),
];

/** Wizard step 1: each column of the file to one field, or left out (PRD §3.13.3 step 2). */
export function ColumnMapTable({ columns, onChange }: ColumnMapTableProps) {
  const used = new Set(Object.values(columns));
  const missing = REQUIRED_FIELDS.filter((f) => !used.has(f));
  return (
    <div className="log-columns">
      <ul className="log-columns__list">
        {Object.entries(columns).map(([header, field]) => (
          <li key={header} className="log-columns__row">
            <SelectField
              label={`Column “${header}”`}
              value={field ?? LEAVE_OUT}
              options={OPTIONS}
              onChange={(v) => onChange(header, v === LEAVE_OUT ? null : v)}
            />
          </li>
        ))}
      </ul>
      <p className="log-columns__note" role="status">
        {missing.length > 0
          ? `Still needed: ${missing.map((f: LogField) => LOG_FIELD_LABELS[f]).join(", ")}.`
          : "Case ID, activity and timestamp are all mapped."}{" "}
        Columns left out are never read.
      </p>
    </div>
  );
}
