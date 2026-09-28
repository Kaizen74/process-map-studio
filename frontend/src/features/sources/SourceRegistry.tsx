import { useState, type MouseEvent } from "react";
import type { Source, SourcePatch } from "../../api/types";
import { Button, Chip } from "../../components/common";
import { KIND_OPTIONS, NOT_MEASURED, coverageText, sourceStatus } from "../../lib/sources";

const DATE = /^\d{4}-\d{2}-\d{2}$/;

export interface SourceRegistryProps {
  sources: readonly Source[];
  selectedId: string | null;
  onOpen: (source: Source) => void;
  onChange: (source: Source, patch: SourcePatch) => void;
  onDelete: (source: Source) => void;
}

/** A field that saves when it loses focus, and only if it changed. */
function BlurText({
  label,
  value,
  type = "text",
  onCommit,
}: {
  label: string;
  value: string;
  type?: "text" | "date";
  onCommit: (value: string) => void;
}) {
  const [draft, setDraft] = useState(value);
  return (
    <input
      className="field__control registry__input"
      type={type}
      value={draft}
      aria-label={label}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={() => {
        const next = draft.trim();
        if (next === value) return;
        if (type === "date" && next && !DATE.test(next)) {
          setDraft(value);
          return;
        }
        onCommit(next);
      }}
    />
  );
}

/** Registry table (PRD §5.4 Sources). Clicking a row, or its file name, opens the source viewer. */
export function SourceRegistry({ sources, selectedId, onOpen, onChange, onDelete }: SourceRegistryProps) {
  function onRowClick(event: MouseEvent, source: Source) {
    if ((event.target as HTMLElement).closest("input, select, button, a, label")) return;
    onOpen(source);
  }

  return (
    <div className="registry">
      <table className="registry__table">
        <caption className="visually-hidden">Sources for this engagement</caption>
        <thead>
          <tr>
            <th scope="col">File</th>
            <th scope="col">Kind</th>
            <th scope="col">Format</th>
            <th scope="col">Version date</th>
            <th scope="col">Owner</th>
            <th scope="col">Controlled copy</th>
            <th scope="col">Status</th>
            <th scope="col">Coverage</th>
            <th scope="col">
              <span className="visually-hidden">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => {
            const status = sourceStatus(source);
            const selected = source.id === selectedId;
            return (
              <tr
                key={source.id}
                className={["registry__row", selected ? "registry__row--selected" : ""].filter(Boolean).join(" ")}
                aria-current={selected ? "true" : undefined}
                onClick={(event) => onRowClick(event, source)}
              >
                <th scope="row">
                  <Button variant="link" className="registry__file" onClick={() => onOpen(source)}>
                    {source.filename}
                  </Button>
                </th>
                <td>
                  <select
                    className="field__control registry__input"
                    value={source.kind}
                    aria-label={`Kind of ${source.filename}`}
                    onChange={(event) => onChange(source, { kind: event.target.value })}
                  >
                    {KIND_OPTIONS.map((kind) => (
                      <option key={kind.value} value={kind.value}>
                        {kind.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="mono">{source.format}</td>
                <td>
                  <BlurText
                    key={source.version_date}
                    type="date"
                    label={`Version date of ${source.filename}`}
                    value={source.version_date}
                    onCommit={(value) => onChange(source, { version_date: value })}
                  />
                </td>
                <td>
                  <BlurText
                    key={source.owner}
                    label={`Owner of ${source.filename}`}
                    value={source.owner}
                    onCommit={(value) => onChange(source, { owner: value })}
                  />
                </td>
                <td>
                  <input
                    type="checkbox"
                    className="registry__check"
                    checked={source.controlled_copy}
                    aria-label={`${source.filename} is a controlled copy`}
                    onChange={(event) => onChange(source, { controlled_copy: event.target.checked })}
                  />
                </td>
                <td>
                  <div className="registry__status">
                    <Chip tone={status.tone} dashed={status.dashed}>
                      {status.label}
                    </Chip>
                    {source.error && <span className="registry__reason">{source.error}</span>}
                  </div>
                </td>
                <td className="mono">
                  {coverageText(source.coverage_pct) ?? (
                    <>
                      <span aria-hidden="true">–</span>
                      <span className="visually-hidden">{NOT_MEASURED}</span>
                    </>
                  )}
                </td>
                <td>
                  <Button variant="danger" aria-label={`Delete ${source.filename}`} onClick={() => onDelete(source)}>
                    Delete
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
