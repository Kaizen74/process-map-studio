import type { ReactNode } from "react";
import type { StepRow, TableFilter } from "../../lib/table";
import type { StanceOrState } from "../../lib/stateGlyph";
import { SegmentedControl, StateGlyph } from "../common";
import "./table.css";

export interface StepTableProps {
  rows: readonly StepRow[];
  filter: TableFilter;
  filters: readonly { value: TableFilter; label: string }[];
  onFilter: (filter: TableFilter) => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** The step being edited in place, and its editor (shown in the row below it). */
  editingId: string | null;
  editor: ReactNode;
  /** Edit in place; omitted where the version can't change. */
  onEditInline?: ((id: string) => void) | undefined;
}

const STATES = new Set(["corroborated", "documented_only", "practiced_only", "contested", "trace_contradicted", "not_assessed"]);
const COLUMNS = ["Step", "Kind", "Lane", "Prov", "Source state", "Time", "Confidence", "Review"];

/**
 * The map as a table (PRD §5.7.4): the accessible equivalent of the map, with filters. Clicking
 * a row selects its step, as on the map; a step can be edited in place.
 */
export function StepTable({
  rows,
  filter,
  filters,
  onFilter,
  selectedId,
  onSelect,
  editingId,
  editor,
  onEditInline,
}: StepTableProps) {
  const span = COLUMNS.length + (onEditInline ? 1 : 0);
  return (
    <div className="step-table">
      <SegmentedControl label="Show" options={filters} value={filter} onChange={onFilter} />
      <div className="step-table__scroll">
        <table className="step-table__table">
          <caption className="visually-hidden">Steps in process order</caption>
          <thead>
            <tr>
              {COLUMNS.map((c) => (
                <th key={c} scope="col">
                  {c}
                </th>
              ))}
              {onEditInline && (
                <th scope="col">
                  <span className="visually-hidden">Edit in place</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={span} className="step-table__empty">
                  No steps match this filter.
                </td>
              </tr>
            )}
            {rows.map((row) => {
              const classes = [
                "step-table__row",
                row.id === selectedId && "step-table__row--selected",
                row.rejected && "step-table__row--rejected",
              ]
                .filter(Boolean)
                .join(" ");
              const state = (STATES.has(row.sourceState) ? row.sourceState : "not_assessed") as StanceOrState;
              return [
                <tr key={row.id} className={classes} onClick={() => onSelect(row.id)}>
                  <th scope="row">
                    <button
                      type="button"
                      className="step-table__step"
                      aria-pressed={row.id === selectedId}
                      onClick={(event) => {
                        event.stopPropagation();
                        onSelect(row.id);
                      }}
                    >
                      {row.label}
                    </button>
                    {row.partOf && <span className="step-table__part-of">{row.partOf}</span>}
                  </th>
                  <td>{row.kind}</td>
                  <td>{row.lane}</td>
                  <td className="mono">{row.provenance}</td>
                  <td>
                    <StateGlyph state={state} />
                  </td>
                  <td className={row.time === "No time stated" ? "mono step-table__danger" : "mono"}>{row.time}</td>
                  <td className="mono">{row.confidence || <span className="step-table__muted">Not worked out</span>}</td>
                  <td className={row.needsCheck ? "step-table__danger" : undefined}>{row.review}</td>
                  {onEditInline && (
                    <td>
                      {!row.rejected && (
                        <button
                          type="button"
                          className="btn btn--link"
                          onClick={(event) => {
                            event.stopPropagation();
                            onEditInline(row.id);
                          }}
                        >
                          Edit in place<span className="visually-hidden">: {row.label}</span>
                        </button>
                      )}
                    </td>
                  )}
                </tr>,
                row.id === editingId && (
                  <tr key={`${row.id}-editor`} className="step-table__editor">
                    <td colSpan={span}>{editor}</td>
                  </tr>
                ),
              ];
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
