import { useState } from "react";
import {
  editFieldOf,
  linesOf,
  toEdit,
  type GuideEdit,
  type GuideRow,
  type GuideTable,
  type GuideView,
  type RowEdit,
} from "../../lib/interview";
import { Button, TextAreaField } from "../common";
import "./interview.css";

// The guide editor (PRD §5.4 Guide tab, criterion 49; C5c): every section as a card, each question
// with its ID, wording, probes and what it is for. Minutes, IDs and the order stay as they are.
// Presentational: the screen saves the edits and passes back any refusal.

export const HELD_BACK_NOTE = "Held back to avoid anchoring the SME: ask only here, after they have described the work.";

export interface GuideEditorProps {
  guide: GuideView;
  busy: boolean;
  /** The server's refusal: its message and the field it names (tables[i].rows[j].…). */
  error?: { message: string; field?: string | undefined } | null | undefined;
  saved: boolean;
  onSave: (body: GuideEdit) => void;
  onClose: () => void;
}

function RowFields({
  row,
  value,
  onChange,
  error,
  where,
}: {
  row: GuideRow;
  value: RowEdit;
  onChange: (next: RowEdit) => void;
  error: [string, string] | null;
  where: string;
}) {
  const name = row.id || `Your question (${where})`;
  const own = !row.id || /^E\d+$/.test(row.id);
  const errorFor = (part: string) => (error && error[0] === part ? error[1] : null);
  return (
    <li className="guide-editor__row">
      <p className="guide-editor__meta">
        <span className="mono">{row.id || "Blank row"}</span>
        {" · "}
        {row.minutes} min
        {row.targets.length > 0 && ` · for: ${row.targets.join("; ")}`}
        {own && row.id && " · your question"}
      </p>
      <TextAreaField
        label={row.id ? `Question ${row.id}` : name}
        value={value.wording}
        rows={2}
        onChange={(wording) => onChange({ ...value, wording })}
        help={row.lead_in || row.note ? [row.lead_in, row.note].filter(Boolean).join(" · ") : undefined}
        error={errorFor("wording") ?? errorFor("id")}
      />
      <TextAreaField
        label={`Probes for ${row.id || name} (one per line)`}
        value={value.probes.join("\n")}
        rows={Math.max(2, value.probes.length)}
        onChange={(text) => onChange({ ...value, probes: linesOf(text) })}
        error={errorFor("probes")}
      />
      {row.held_back.length > 0 && (
        <TextAreaField
          label={`Held-back probes for ${row.id} (one per line)`}
          value={value.held_back.join("\n")}
          rows={Math.max(2, value.held_back.length)}
          onChange={(text) => onChange({ ...value, held_back: linesOf(text) })}
          help={HELD_BACK_NOTE}
          error={errorFor("held_back")}
        />
      )}
    </li>
  );
}

function TableCard({
  table,
  index,
  value,
  onChange,
  error,
}: {
  table: GuideTable;
  index: number;
  value: RowEdit[];
  onChange: (rows: RowEdit[]) => void;
  error: [number, number, string, string] | null;
}) {
  const titleId = `guide-section-${index}`;
  return (
    <section className="guide-editor__section" aria-labelledby={titleId}>
      <h3 id={titleId} className="guide-editor__title">
        {table.label} <span className="mono">({table.minutes} min)</span>
      </h3>
      {table.note && <p className="guide-editor__meta">{table.note}</p>}
      <ol className="guide-editor__rows">
        {table.rows.map((row, ri) => (
          <RowFields
            key={`${ri}-${row.id}`}
            row={row}
            value={value[ri] ?? { id: row.id, wording: "", probes: [], held_back: [] }}
            where={`${table.label}, row ${ri + 1}`}
            error={error && error[1] === ri ? [error[2], error[3]] : null}
            onChange={(next) => onChange(value.map((v, i) => (i === ri ? next : v)))}
          />
        ))}
      </ol>
    </section>
  );
}

/** Edit a tailored guide, then save; the downloads give the saved version. */
export function GuideEditor({ guide, busy, error, saved, onSave, onClose }: GuideEditorProps) {
  const [draft, setDraft] = useState<GuideEdit>(() => toEdit(guide.document));
  const at = editFieldOf(error?.field);
  const located: [number, number, string, string] | null = at && error ? [at[0], at[1], at[2], error.message] : null;
  return (
    <form
      className="guide-editor"
      aria-label={`Edit ${guide.document.title}`}
      onSubmit={(event) => {
        event.preventDefault();
        if (!busy) onSave(draft);
      }}
    >
      <p className="interview-tip">
        Version {guide.version}
        {guide.edited ? " (edited)" : ""}. Change the wording or the probes, or write your own questions into blank rows.
        Question IDs and minutes stay as they are, so the plan still adds up. Making a new version later starts again from
        the template and keeps this one.
      </p>
      {guide.document.generation_note && <p className="interview-note">{guide.document.generation_note}</p>}
      {(guide.suggested_probes?.length ?? 0) > 0 && (
        <section className="guide-probes" aria-labelledby="guide-probes-title">
          <h3 id="guide-probes-title">Suggested probes from Capability Compass</h3>
          <p className="interview-tip">
            Prompts only, to use if they help in the interview. They are not questions of this guide and nothing here
            is evidence: only what the SME says, once checked against the transcript, reaches the map.
          </p>
          <ul>
            {guide.suggested_probes?.map((probe) => <li key={probe}>{probe}</li>)}
          </ul>
        </section>
      )}
      {guide.document.tables.map((table, ti) => (
        <TableCard
          key={table.label}
          table={table}
          index={ti}
          value={draft.tables[ti]?.rows ?? []}
          error={located && located[0] === ti ? located : null}
          onChange={(rows) =>
            setDraft({ tables: draft.tables.map((t, i) => (i === ti ? { ...t, rows } : t)) })
          }
        />
      ))}
      {error && !located && (
        <p className="panel-danger" role="alert">
          {error.message}
        </p>
      )}
      {located && (
        <p className="panel-danger" role="alert">
          Not saved: {located[3]} See the highlighted question.
        </p>
      )}
      {saved && !error && (
        <p className="guide-editor__meta" role="status">
          Saved.
        </p>
      )}
      <div className="profile-form__actions">
        <Button type="submit" variant="primary" aria-busy={busy}>
          {busy ? "Saving…" : "Save guide"}
        </Button>
        <Button onClick={onClose}>Close editor</Button>
      </div>
    </form>
  );
}
