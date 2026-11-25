import { useState, type MouseEvent } from "react";
import type { Role, SopEntry, Source, SourcePatch } from "../../api/types";
import { Button, Chip } from "../../components/common";
import {
  CHECK_ROLE,
  KIND_OPTIONS,
  NOT_MEASURED,
  OLDER_VERSION,
  coverageText,
  isSop,
  sourceStatus,
} from "../../lib/sources";

const DATE = /^\d{4}-\d{2}-\d{2}$/;

export interface SourceRegistryProps {
  sources: readonly Source[];
  selectedId: string | null;
  onOpen: (source: Source) => void;
  onChange: (source: Source, patch: SourcePatch) => void;
  onDelete: (source: Source) => void;
  /** §3.20: the engagement's roles, for an SOP's owner and the role that updates it. */
  roles?: readonly Role[];
  /** §3.20: the SOP register's entries (overdue, older version), by source. */
  register?: readonly SopEntry[];
}

const OTHER = "__other";

/**
 * §3.20 (DECISIONS 110): a role of the engagement, or another role's name typed. An owner typed
 * before the register existed is kept and marked "check: is this a role?" until Eric confirms or
 * changes it; it is never converted on its own.
 */
function RoleChoice({
  label,
  textLabel,
  roleId,
  text,
  unchecked,
  roles,
  onRole,
  onText,
  onConfirm,
}: {
  label: string;
  textLabel: string;
  roleId: string | null;
  text: string;
  unchecked: boolean;
  roles: readonly Role[];
  onRole: (roleId: string | null) => void;
  onText: (text: string) => void;
  onConfirm?: () => void;
}) {
  const [typing, setTyping] = useState(false);
  const known = roleId !== null && roles.some((r) => r.id === roleId);
  const value = known ? (roleId ?? "") : text || typing ? OTHER : "";
  return (
    <div className="registry__role">
      <select
        className="field__control registry__input"
        value={value}
        aria-label={label}
        onChange={(event) => {
          const next = event.target.value;
          setTyping(next === OTHER);
          if (next === OTHER) return;
          onRole(next || null);
        }}
      >
        <option value="">Not recorded</option>
        {roles.map((r) => (
          <option key={r.id} value={r.id}>
            {r.name}
          </option>
        ))}
        <option value={OTHER}>Other role…</option>
      </select>
      {value === OTHER && <BlurText key={text} label={textLabel} value={text} onCommit={onText} />}
      {value === OTHER && text && unchecked && (
        <span className="registry__check-role">
          <span className="registry__reason">{CHECK_ROLE}</span>
          {onConfirm && (
            <Button variant="link" onClick={onConfirm}>
              It is a role
            </Button>
          )}
        </span>
      )}
    </div>
  );
}

function NotApplicable() {
  return (
    <>
      <span aria-hidden="true">–</span>
      <span className="visually-hidden">Only for SOPs and manuals</span>
    </>
  );
}

/** A field that saves when it loses focus, and only if it changed. */
function BlurText({
  label,
  value,
  type = "text",
  placeholder,
  onCommit,
}: {
  label: string;
  value: string;
  type?: "text" | "date";
  placeholder?: string;
  onCommit: (value: string) => void;
}) {
  const [draft, setDraft] = useState(value);
  return (
    <input
      className="field__control registry__input"
      type={type}
      value={draft}
      aria-label={label}
      placeholder={placeholder}
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
export function SourceRegistry({
  sources,
  selectedId,
  onOpen,
  onChange,
  onDelete,
  roles = [],
  register = [],
}: SourceRegistryProps) {
  const people = roles.filter((r) => !r.is_system);
  const entryOf = (id: string) => register.find((e) => e.source_id === id);
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
            <th scope="col">Updated by</th>
            <th scope="col">Last reviewed</th>
            <th scope="col">Review due</th>
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
            const sop = isSop(source);
            const entry = entryOf(source.id);
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
                  {sop && (
                    <BlurText
                      key={`title-${source.title ?? ""}`}
                      label={`Title of ${source.filename}`}
                      placeholder="Its own title, if different"
                      value={source.title ?? ""}
                      onCommit={(value) => onChange(source, { title: value })}
                    />
                  )}
                  {entry?.older && <span className="registry__reason">{OLDER_VERSION}</span>}
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
                  {sop ? (
                    <RoleChoice
                      label={`Owner role of ${source.filename}`}
                      textLabel={`Owner of ${source.filename}`}
                      roleId={source.owner_role_id ?? null}
                      text={source.owner_role_id ? "" : source.owner}
                      unchecked={!source.owner_checked}
                      roles={people}
                      onRole={(id) => onChange(source, id ? { owner_role_id: id } : { owner_role_id: null, owner: "" })}
                      onText={(value) => onChange(source, { owner: value })}
                      onConfirm={() => onChange(source, { owner_checked: true })}
                    />
                  ) : (
                    <BlurText
                      key={source.owner}
                      label={`Owner of ${source.filename}`}
                      value={source.owner}
                      onCommit={(value) => onChange(source, { owner: value })}
                    />
                  )}
                </td>
                <td>
                  {sop ? (
                    <RoleChoice
                      label={`Role that updates ${source.filename}`}
                      textLabel={`Other role that updates ${source.filename}`}
                      roleId={source.updated_by_role_id ?? null}
                      text={source.updated_by_other ?? ""}
                      unchecked={false}
                      roles={people}
                      onRole={(id) =>
                        onChange(source, id ? { updated_by_role_id: id } : { updated_by_role_id: null, updated_by_other: "" })
                      }
                      onText={(value) => onChange(source, { updated_by_other: value })}
                    />
                  ) : (
                    <NotApplicable />
                  )}
                </td>
                <td>
                  {sop ? (
                    <BlurText
                      key={`reviewed-${source.last_reviewed ?? ""}`}
                      label={`Last reviewed, ${source.filename}`}
                      placeholder="YYYY-MM"
                      value={source.last_reviewed ?? ""}
                      onCommit={(value) => onChange(source, { last_reviewed: value })}
                    />
                  ) : (
                    <NotApplicable />
                  )}
                </td>
                <td>
                  {sop ? (
                    <>
                      <BlurText
                        key={`due-${source.review_due ?? ""}`}
                        label={`Review due, ${source.filename}`}
                        placeholder="YYYY-MM"
                        value={source.review_due ?? ""}
                        onCommit={(value) => onChange(source, { review_due: value })}
                      />
                      {entry?.overdue && <span className="registry__reason">Overdue</span>}
                    </>
                  ) : (
                    <NotApplicable />
                  )}
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
