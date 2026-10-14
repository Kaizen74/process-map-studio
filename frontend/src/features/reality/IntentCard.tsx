import { useState } from "react";
import { Button, Card, SelectField, TextField } from "../../components/common";
import { useRoles } from "../../hooks/useRoles";
import { useAddIntent, useExtractIntent, useIntent, useUpdateIntent } from "../../hooks/useReality";
import { messageOf } from "../../lib/errors";
import { KIND_LABELS, RESULT_LABELS, type IntentStatement, type RealitySnapshot } from "../../lib/reality";

const METRICS = [
  { value: "cycle_time_min", label: "Cycle time (minutes)" },
  { value: "step_time_min", label: "Step time (minutes)" },
  { value: "wait_min", label: "Waiting time (minutes)" },
  { value: "lead_time_min", label: "Ready before departure (minutes)" },
  { value: "straight_through_pct", label: "Straight through (%)" },
  { value: "recorded_pct", label: "Recorded (%)" },
];
const COMPARATORS = [
  { value: "at_most", label: "At most" },
  { value: "at_least", label: "At least" },
  { value: "equals", label: "Exactly" },
];
const STATUS_ORDER = ["proposed", "confirmed", "dismissed"] as const;
const STATUS_TITLES: Readonly<Record<string, string>> = {
  proposed: "Proposed: confirm or dismiss",
  confirmed: "Confirmed",
  dismissed: "Dismissed",
};

interface TargetForm {
  text: string;
  metric: string;
  comparator: string;
  value: string;
  owner: string;
  date: string;
}

const EMPTY: TargetForm = { text: "", metric: "cycle_time_min", comparator: "at_most", value: "", owner: "", date: "" };

/**
 * The Intent card (PRD §5.4 Reality): intent statements found in policy or charter documents
 * (proposed until Eric confirms them) and the targets he states as the owner. Intent is evidence:
 * never drawn from interviews, never invented (constraint 25).
 */
export function IntentCard({ engagementId, snapshot }: { engagementId: string; snapshot: RealitySnapshot }) {
  const statements = useIntent(engagementId);
  const roles = useRoles(engagementId);
  const update = useUpdateIntent(engagementId);
  const add = useAddIntent(engagementId);
  const extract = useExtractIntent(engagementId);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState<TargetForm>(EMPTY);
  const results = new Map(snapshot.intents.map((i) => [i.id, i]));
  const owners = (roles.data ?? []).filter((r) => !r.is_system).map((r) => ({ value: r.id, label: r.name }));

  const save = () => {
    add.mutate(
      {
        scope: "process",
        kind: "target",
        text: form.text,
        metric: form.metric,
        comparator: form.comparator,
        target_value: form.value === "" ? null : Number(form.value),
        unit: form.metric.endsWith("_pct") ? "%" : "min",
        owner_role_id: form.owner,
        stated_on: form.date,
      },
      {
        onSuccess: () => {
          setAdding(false);
          setForm(EMPTY);
        },
      },
    );
  };

  return (
    <Card
      title="Intent"
      description="What the organisation promises, targets and controls: quoted from a policy or charter, or stated by the process owner. Nothing proposed counts until you confirm it."
    >
      {statements.isError && <p className="danger-note">{messageOf(statements.error)}</p>}
      {statements.data?.length === 0 && (
        <p className="inline-note">
          No intent yet. Find it in a policy or charter you uploaded, or add a target the process owner states.
        </p>
      )}
      {STATUS_ORDER.map((status) => {
        const rows = (statements.data ?? []).filter((s) => s.status === status && s.verification_status !== "rejected");
        if (rows.length === 0) return null;
        return (
          <section key={status} className="intent-group" aria-label={STATUS_TITLES[status]}>
            <h3 className="intent-group__title">{STATUS_TITLES[status]}</h3>
            <ul className="intent-list">
              {rows.map((s) => (
                <IntentRow
                  key={s.id}
                  statement={s}
                  result={results.get(s.id)?.result}
                  busy={update.isPending}
                  onStatus={(next) => update.mutate({ id: s.id, status: next })}
                />
              ))}
            </ul>
          </section>
        );
      })}
      {update.isError && <p className="danger-note">{messageOf(update.error)}</p>}
      <div className="intent-actions">
        <Button onClick={extract.start} disabled={extract.running}>
          {extract.running ? "Reading your documents…" : "Find intent in documents"}
        </Button>
        {!adding && <Button onClick={() => setAdding(true)}>Add a target</Button>}
      </div>
      {extract.running && (
        <p className="inline-note" role="status">
          Reading your policy and charter documents. Proposed statements appear here when the reading ends.
        </p>
      )}
      {extract.outcome && (
        <p className={extract.outcome.failed ? "danger-note" : "inline-note"} role="status">
          {extract.outcome.message}
        </p>
      )}
      {extract.error && <p className="danger-note">{messageOf(extract.error)}</p>}
      {adding && (
        <form
          className="intent-form"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <TextField label="Target, in the owner's words" value={form.text} onChange={(v) => setForm({ ...form, text: v })} />
          <SelectField label="Measure" value={form.metric} options={METRICS} onChange={(v) => setForm({ ...form, metric: v })} />
          <SelectField label="Comparison" value={form.comparator} options={COMPARATORS} onChange={(v) => setForm({ ...form, comparator: v })} />
          <TextField label="Value" value={form.value} onChange={(v) => setForm({ ...form, value: v })} />
          <SelectField
            label="Owner's role"
            value={form.owner}
            options={[{ value: "", label: "Choose a role" }, ...owners]}
            onChange={(v) => setForm({ ...form, owner: v })}
          />
          <TextField label="Stated on (YYYY-MM-DD)" value={form.date} onChange={(v) => setForm({ ...form, date: v })} />
          {add.isError && <p className="danger-note">{messageOf(add.error)}</p>}
          <div className="intent-actions">
            <Button variant="primary" type="submit" disabled={add.isPending}>
              Save target
            </Button>
            <Button onClick={() => setAdding(false)}>Cancel</Button>
          </div>
        </form>
      )}
    </Card>
  );
}

interface RowProps {
  statement: IntentStatement;
  result: string | undefined;
  busy: boolean;
  onStatus: (status: string) => void;
}

function IntentRow({ statement: s, result, busy, onStatus }: RowProps) {
  return (
    <li className="intent-row">
      <span className="intent-row__kind">{KIND_LABELS[s.kind] ?? s.kind}</span>
      <span className="intent-row__text">{s.text}</span>
      <span className="intent-row__meta">
        {s.origin === "owner_stated" ? `Stated by ${s.owner_role_name || "the owner"}` : `${s.source_name} ${s.anchor}`}
        {s.status === "confirmed" && result && ` · ${RESULT_LABELS[result] ?? result}`}
      </span>
      <span className="intent-row__actions">
        {s.status !== "confirmed" && (
          <Button onClick={() => onStatus("confirmed")} disabled={busy}>
            Confirm{" "}
            <span className="visually-hidden">“{s.text}”</span>
          </Button>
        )}
        {s.status !== "dismissed" && (
          <Button onClick={() => onStatus("dismissed")} disabled={busy}>
            Dismiss{" "}
            <span className="visually-hidden">“{s.text}”</span>
          </Button>
        )}
      </span>
    </li>
  );
}
