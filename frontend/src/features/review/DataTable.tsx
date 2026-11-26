import { useSetDataMove, useSetPaperDecider, useSetSystemOfRecord } from "../../hooks/useReview";
import { DATA_MOVES, dataMoveWord, handoffsFrom, systemWord } from "../../lib/accountability";
import { messageOf } from "../../lib/errors";
import type { DataMove, Graph, GraphElement } from "../../lib/mapTypes";

// The data fields of every step in one table (DECISIONS 113): the decider named in the documents,
// the system of record and how data moves at each handoff, saved as soon as one is chosen. The
// passage naming the decider, another system's name and what checks a handoff stay in the step's
// panel. Read only where the version can't change.

const STEP_KINDS = new Set(["activity", "decision", "approval"]);
const DECIDING = new Set(["decision", "approval"]);
const NOT_RECORDED = "";
const NOT_NAMED = "__not_named";
const NONE = "__none";
const OTHER = "__other";

export interface DataTableProps {
  graph: Graph;
  versionId: string;
  engagementId: string;
  editable: boolean;
  onSelect: (id: string) => void;
}

export function DataTable({ graph, versionId, engagementId, editable, onSelect }: DataTableProps) {
  const paper = useSetPaperDecider(versionId, engagementId);
  const system = useSetSystemOfRecord(versionId, engagementId);
  const move = useSetDataMove(versionId, engagementId);
  const steps = graph.elements.filter((e) => STEP_KINDS.has(e.kind) && e.review_status !== "rejected");
  const people = graph.roles.filter((r) => !r.is_system);
  const systems = graph.roles.filter((r) => r.is_system);
  const failed = paper.error ?? system.error ?? move.error;
  return (
    <div className="table-view">
      <p className="interview-tip">
        Choose from the lists to record each field; it is saved at once. The passage that names a decider, another
        system&apos;s name and what checks a handoff are recorded in the step&apos;s panel.
      </p>
      {failed && (
        <p className="field__error" role="alert">
          {messageOf(failed)}
        </p>
      )}
      <div className="registry">
        <table className="registry__table">
          <caption className="visually-hidden">The data fields of each step</caption>
          <thead>
            <tr>
              <th scope="col">Step</th>
              <th scope="col">Decider named in the documents</th>
              <th scope="col">System of record</th>
              <th scope="col">How data moves at each handoff</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((e) => (
              <tr key={e.id}>
                <th scope="row">
                  <button type="button" className="btn btn--link" onClick={() => onSelect(e.id)}>
                    {e.code ? `${e.code} ` : ""}
                    {e.label}
                  </button>
                </th>
                <td>
                  {DECIDING.has(e.kind) ? (
                    editable ? (
                      <select
                        className="field__control registry__input"
                        aria-label={`Decider named in the documents for ${e.label}`}
                        value={paperValue(e)}
                        disabled={paper.isPending}
                        onChange={(event) => {
                          const v = event.target.value;
                          const body =
                            v === NOT_RECORDED
                              ? { status: null }
                              : v === NOT_NAMED
                                ? { status: "not_named" as const }
                                : { status: "named" as const, role_id: v, segment_id: e.paper_decider?.segment_id ?? null };
                          paper.mutate({ elementId: e.id, body });
                        }}
                      >
                        <option value={NOT_RECORDED}>Not recorded</option>
                        {people.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name}
                          </option>
                        ))}
                        <option value={NOT_NAMED}>Not named in any document</option>
                      </select>
                    ) : (
                      paperWord(e, graph)
                    )
                  ) : (
                    <>
                      <span aria-hidden="true">–</span>
                      <span className="visually-hidden">Only for decisions and approvals</span>
                    </>
                  )}
                </td>
                <td>
                  {editable ? (
                    <select
                      className="field__control registry__input"
                      aria-label={`System of record for ${e.label}`}
                      value={systemValue(e)}
                      disabled={system.isPending}
                      onChange={(event) => {
                        const v = event.target.value;
                        if (v === OTHER) return; // kept as it is; changed in the panel
                        const body =
                          v === NOT_RECORDED
                            ? { status: null }
                            : v === NONE
                              ? { status: "none" as const }
                              : { status: "system" as const, role_id: v };
                        system.mutate({ elementId: e.id, body });
                      }}
                    >
                      <option value={NOT_RECORDED}>Not recorded</option>
                      {systems.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name}
                        </option>
                      ))}
                      {e.system_of_record?.status === "other" && (
                        <option value={OTHER}>{e.system_of_record.other} (other system)</option>
                      )}
                      <option value={NONE}>None: paper or memory</option>
                    </select>
                  ) : (
                    systemWord(e.system_of_record ?? null, graph.roles)
                  )}
                </td>
                <td>
                  <Handoffs
                    element={e}
                    graph={graph}
                    editable={editable}
                    busy={move.isPending}
                    onMove={(edgeId, dataMove) => move.mutate({ edgeId, dataMove })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Handoffs({
  element,
  graph,
  editable,
  busy,
  onMove,
}: {
  element: GraphElement;
  graph: Graph;
  editable: boolean;
  busy: boolean;
  onMove: (edgeId: string, dataMove: DataMove | null) => void;
}) {
  const found = handoffsFrom(element, graph.elements, graph.edges, new Set());
  if (found.length === 0) {
    return (
      <>
        <span aria-hidden="true">–</span>
        <span className="visually-hidden">No handoff from this step</span>
      </>
    );
  }
  return (
    <ul className="data-table__handoffs">
      {found.map((h) => (
        <li key={h.edge.id}>
          {editable ? (
            <span className="data-table__handoff">
              <span className="data-table__to" aria-hidden="true">
                To {h.toLabel}
              </span>
              <select
                className="field__control registry__input"
                aria-label={`How data moves from ${element.label} to ${h.toLabel}`}
                value={h.edge.data_move ?? ""}
                disabled={busy}
                onChange={(event) => onMove(h.edge.id, (event.target.value || null) as DataMove | null)}
              >
                <option value="">Not known</option>
                {DATA_MOVES.map((m) => (
                  <option key={m} value={m}>
                    {dataMoveWord(m)}
                  </option>
                ))}
              </select>
            </span>
          ) : (
            `To ${h.toLabel}: ${dataMoveWord(h.edge.data_move ?? null)}`
          )}
        </li>
      ))}
    </ul>
  );
}

function paperValue(e: GraphElement): string {
  const p = e.paper_decider ?? null;
  if (p === null) return NOT_RECORDED;
  return p.status === "not_named" ? NOT_NAMED : (p.role_id ?? NOT_RECORDED);
}

function paperWord(e: GraphElement, graph: Graph): string {
  const p = e.paper_decider ?? null;
  if (p === null) return "Not recorded";
  if (p.status === "not_named") return "Not named in any document";
  return graph.roles.find((r) => r.id === p.role_id)?.name ?? "Not recorded";
}

function systemValue(e: GraphElement): string {
  const s = e.system_of_record ?? null;
  if (s === null) return NOT_RECORDED;
  if (s.status === "none") return NONE;
  if (s.status === "other") return OTHER;
  return s.role_id ?? NOT_RECORDED;
}
