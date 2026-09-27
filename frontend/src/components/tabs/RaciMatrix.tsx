import type { Graph } from "../../lib/mapTypes";
import "./tabs.css";

export interface RaciMatrixProps {
  graph: Graph;
  /** Role IDs in lane order: the matrix's columns start with these. */
  laneOrder: readonly string[];
  selectedId: string | null;
  onSelect: (elementId: string) => void;
}

const STEPS = new Set(["activity", "decision", "approval"]);

/**
 * Steps × roles (PRD §5.7.10): mono letters, A in weight 500, a contested A as `A?` in danger
 * text, "·" where a role has no part. Rejected rows are faded and struck through; the selected row
 * is tinted; clicking a row selects its step.
 */
export function RaciMatrix({ graph, laneOrder, selectedId, onSelect }: RaciMatrixProps) {
  const steps = graph.elements.filter((e) => STEPS.has(e.kind));
  const used = new Set(steps.flatMap((e) => e.raci.map((r) => r.role_id)));
  const names = new Map(graph.roles.map((r) => [r.id, r.name]));
  const columns = [...laneOrder.filter((id) => used.has(id)), ...[...used].filter((id) => !laneOrder.includes(id))];
  return (
    <div className="raci">
      <table className="raci__table">
        <caption className="raci__caption">
          R responsible · A accountable · C consulted · I informed. <span className="raci__contested">A?</span> means
          the sources disagree about who is accountable.
        </caption>
        <thead>
          <tr>
            <th scope="col">Step</th>
            {columns.map((id) => (
              <th key={id} scope="col">
                {names.get(id) ?? "Unknown role"}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {steps.map((step) => {
            const classes = [
              "raci__row",
              step.id === selectedId && "raci__row--selected",
              step.review_status === "rejected" && "raci__row--rejected",
            ]
              .filter(Boolean)
              .join(" ");
            return (
              <tr key={step.id} className={classes} onClick={() => onSelect(step.id)}>
                <th scope="row">
                  <button type="button" className="raci__step" aria-pressed={step.id === selectedId} onClick={(e) => {
                    e.stopPropagation();
                    onSelect(step.id);
                  }}>
                    {step.label}
                  </button>
                </th>
                {columns.map((id) => {
                  const letters = step.raci.filter((r) => r.role_id === id);
                  return (
                    <td key={id} className="mono">
                      {letters.length === 0 ? (
                        <>
                          <span className="raci__none" aria-hidden="true">
                            ·
                          </span>
                          <span className="visually-hidden">none</span>
                        </>
                      ) : (
                        letters.map((r, i) => (
                          <span
                            key={i}
                            className={[
                              "raci__letter",
                              r.letter === "A" && "raci__letter--a",
                              r.letter === "A" && r.contested && "raci__contested",
                            ]
                              .filter(Boolean)
                              .join(" ")}
                          >
                            {r.letter === "A" && r.contested ? "A?" : r.letter}
                          </span>
                        ))
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
