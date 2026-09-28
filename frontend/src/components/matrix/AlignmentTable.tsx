import { COLUMNS, divergenceLabel, type AlignmentRow } from "../../lib/matrix";
import { Button, StateGlyph } from "../common";
import "./matrix.css";

export interface AlignmentTableProps {
  rows: readonly AlignmentRow[];
  onOpen: (elementId: string) => void;
}

/**
 * The alignment matrix (PRD §5.4 Matrix): one row per step, a sticky step column and header; each
 * cell is a state glyph with its words (never colour alone). Silence is shown as silent, never as
 * contradiction. The step name (or anywhere in its row) opens the step.
 */
export function AlignmentTable({ rows, onOpen }: AlignmentTableProps) {
  return (
    <div className="matrix" tabIndex={0} role="region" aria-label="Alignment matrix, scrolls sideways">
      <table className="matrix__table">
        <caption className="visually-hidden">How each kind of source stands on each step</caption>
        <thead>
          <tr>
            <th scope="col" className="matrix__step">
              Step
            </th>
            {COLUMNS.map((c) => (
              <th key={c.key} scope="col">
                {c.label}
              </th>
            ))}
            <th scope="col">State</th>
            <th scope="col">Divergence</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.element_id} className="matrix__row" onClick={() => onOpen(row.element_id)}>
              <th scope="row" className="matrix__step">
                <Button
                  variant="link"
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpen(row.element_id);
                  }}
                >
                  {row.label}
                </Button>
              </th>
              {COLUMNS.map((c) => (
                <td key={c.key}>
                  <StateGlyph state={row[c.key]} />
                </td>
              ))}
              <td>
                <StateGlyph state={row.state} />
              </td>
              <td>
                {row.divergence_types.length === 0 ? (
                  <span className="matrix__none">None</span>
                ) : (
                  <ul className="matrix__types">
                    {row.divergence_types.map((t) => (
                      <li key={t} className="chip chip--danger">
                        {divergenceLabel(t)}
                      </li>
                    ))}
                  </ul>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
