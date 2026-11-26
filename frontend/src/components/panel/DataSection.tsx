import { useState } from "react";
import type { DataMove, GraphEdge, GraphElement, GraphRole, SystemOfRecord } from "../../lib/mapTypes";
import { DATA_MOVES, dataMoveWord, systemWord } from "../../lib/accountability";
import { Button, SelectField, TextField } from "../common";
import { PanelSection as Section } from "./PanelSections";

// The data lens (PRD §3.20; DECISIONS 110): the step's system of record and, for each handoff it
// starts (a line to a step in another lane), how the data moves. Eric's record only: a system log
// that records the receiving step suggests "System interface", never sets it. Presentational: the
// screen saves the choice.

const NOT_RECORDED = "";
const OTHER = "__other";
const NONE = "__none";

export interface Handoff {
  edge: GraphEdge;
  toLabel: string;
  /** A system log records the receiving step (R8 system traces). */
  logged: boolean;
}

export interface DataChoice {
  busy: boolean;
  error?: string | null | undefined;
  onSystem: (body: { status: SystemOfRecord["status"] | null; role_id?: string | null; other?: string }) => void;
  onMove: (edgeId: string, move: DataMove | null) => void;
  /** DECISIONS 113: what checks the data at a handoff ("" clears it). */
  onCheck?: (edgeId: string, check: string) => void;
}

export interface DataSectionProps {
  element: GraphElement;
  roles: readonly GraphRole[];
  handoffs: readonly Handoff[];
  /** Omitted where the version can't change. */
  choice?: DataChoice | undefined;
}

export function DataSection({ element, roles, handoffs, choice }: DataSectionProps) {
  const [editing, setEditing] = useState(false);
  const record = element.system_of_record ?? null;
  return (
    <Section title="Data">
      <dl className="panel-rows">
        <div>
          <dt>System of record</dt>
          <dd>{systemWord(record, roles)}</dd>
        </div>
        {handoffs.map((h) => (
          <div key={h.edge.id}>
            <dt>Data to {h.toLabel}</dt>
            <dd>
              {dataMoveWord(h.edge.data_move ?? null)}
              {h.edge.information_payload && <span className="data-section__more">What moves: {h.edge.information_payload}</span>}
              {h.edge.data_check && <span className="data-section__more">What checks it: {h.edge.data_check}</span>}
            </dd>
          </div>
        ))}
      </dl>
      {handoffs
        .filter((h) => h.logged && !h.edge.data_move)
        .map((h) => (
          <div key={`suggest-${h.edge.id}`} className="inline-note">
            <p>A system log records {h.toLabel}. Suggested: System interface.</p>
            {choice && (
              <Button disabled={choice.busy} onClick={() => choice.onMove(h.edge.id, "system_interface")}>
                Use System interface for {h.toLabel}
              </Button>
            )}
          </div>
        ))}
      {choice && !editing && (
        <div className="work-type-choice__actions">
          <Button disabled={choice.busy} onClick={() => setEditing(true)}>
            {record || handoffs.some((h) => h.edge.data_move) ? "Change the data record" : "Record the data"}
          </Button>
        </div>
      )}
      {choice && editing && (
        <DataForm record={record} roles={roles} handoffs={handoffs} choice={choice} onDone={() => setEditing(false)} />
      )}
      {choice?.error && (
        <p className="panel-danger" role="alert">
          {choice.error}
        </p>
      )}
    </Section>
  );
}

function DataForm({
  record,
  roles,
  handoffs,
  choice,
  onDone,
}: {
  record: SystemOfRecord | null;
  roles: readonly GraphRole[];
  handoffs: readonly Handoff[];
  choice: DataChoice;
  onDone: () => void;
}) {
  const systems = roles.filter((r) => r.is_system);
  const [system, setSystem] = useState(
    record === null
      ? NOT_RECORDED
      : record.status === "none"
        ? NONE
        : record.status === "other"
          ? OTHER
          : (record.role_id ?? NOT_RECORDED),
  );
  const [other, setOther] = useState(record?.other ?? "");
  const [moves, setMoves] = useState<Record<string, string>>(
    Object.fromEntries(handoffs.map((h) => [h.edge.id, h.edge.data_move ?? ""])),
  );
  const [checks, setChecks] = useState<Record<string, string>>(
    Object.fromEntries(handoffs.map((h) => [h.edge.id, h.edge.data_check ?? ""])),
  );
  const [problem, setProblem] = useState<string | null>(null);
  return (
    <form
      className="stack work-type-choice"
      onSubmit={(event) => {
        event.preventDefault();
        if (system === OTHER && !other.trim()) {
          setProblem("Type the other system's name, or choose another answer.");
          return;
        }
        const before =
          record === null ? NOT_RECORDED : record.status === "none" ? NONE : record.status === "other" ? OTHER : record.role_id;
        if (system !== before || (system === OTHER && other.trim() !== (record?.other ?? ""))) {
          if (system === NOT_RECORDED) choice.onSystem({ status: null });
          else if (system === NONE) choice.onSystem({ status: "none" });
          else if (system === OTHER) choice.onSystem({ status: "other", other: other.trim() });
          else choice.onSystem({ status: "system", role_id: system });
        }
        for (const h of handoffs) {
          const next = moves[h.edge.id] ?? "";
          if (next !== (h.edge.data_move ?? "")) choice.onMove(h.edge.id, (next || null) as DataMove | null);
          const check = (checks[h.edge.id] ?? "").trim();
          if (choice.onCheck && check !== (h.edge.data_check ?? "")) choice.onCheck(h.edge.id, check);
        }
        onDone();
      }}
    >
      <SelectField
        label="System of record"
        value={system}
        options={[
          { value: NOT_RECORDED, label: "Not recorded" },
          ...systems.map((r) => ({ value: r.id, label: r.name })),
          { value: OTHER, label: "Other system…" },
          { value: NONE, label: "None: paper or memory" },
        ]}
        onChange={(value) => {
          setSystem(value);
          setProblem(null);
        }}
        help={systems.length === 0 ? "No lane is marked as a system yet; choose Other system… to name one." : undefined}
      />
      {system === OTHER && (
        <TextField label="The other system's name" value={other} onChange={setOther} error={problem} />
      )}
      {handoffs.map((h) => (
        <SelectField
          key={h.edge.id}
          label={`How the data moves to ${h.toLabel}`}
          value={moves[h.edge.id] ?? ""}
          options={[{ value: "", label: "Not known" }, ...DATA_MOVES.map((m) => ({ value: m, label: dataMoveWord(m) }))]}
          onChange={(value) => setMoves((current) => ({ ...current, [h.edge.id]: value }))}
          help={h.logged ? "A system log records this step: System interface is suggested." : undefined}
        />
      ))}
      {choice.onCheck &&
        handoffs.map((h) => (
          <TextField
            key={`check-${h.edge.id}`}
            label={`What checks the data going to ${h.toLabel}`}
            value={checks[h.edge.id] ?? ""}
            onChange={(value) => setChecks((current) => ({ ...current, [h.edge.id]: value }))}
            help="Optional, one line: for example, the weight is checked against the booking."
            error={null}
          />
        ))}
      <div className="work-type-choice__actions">
        <Button type="submit" variant="primary" disabled={choice.busy}>
          Save
        </Button>
        <Button onClick={onDone}>Cancel</Button>
      </div>
    </form>
  );
}
