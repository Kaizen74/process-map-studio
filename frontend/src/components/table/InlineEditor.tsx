import type { FormEvent } from "react";
import type { StepForm } from "../../lib/stepForm";
import { Button, SelectField, TextField } from "../common";

export interface InlineEditorProps {
  label: string;
  form: StepForm;
  errors: Record<string, string>;
  roles: readonly { id: string; name: string }[];
  saving: boolean;
  /** A problem that isn't about one of these fields, e.g. one only the full edit form can fix. */
  problem: string | null;
  onChange: (form: StepForm) => void;
  onSave: () => void;
  onCancel: () => void;
  onOpenFull: () => void;
}

/**
 * Editing a step in place in the table (PRD §5.7.4): name, Responsible, Accountable, time and
 * KPI, with the same field rules as the edit form. Everything else is in the full edit form.
 */
export function InlineEditor({
  label,
  form,
  errors,
  roles,
  saving,
  problem,
  onChange,
  onSave,
  onCancel,
  onOpenFull,
}: InlineEditorProps) {
  const set = <K extends keyof StepForm>(key: K, value: StepForm[K]) => onChange({ ...form, [key]: value });
  const err = (key: string) => errors[key] ?? null;
  const options = roles.map((r) => ({ value: r.id, label: r.name }));
  const contested = form.accountable.length > 1;

  function submit(event: FormEvent) {
    event.preventDefault();
    onSave();
  }

  return (
    <form className="inline-editor" aria-label={`Edit ${label} in place`} onSubmit={submit} noValidate>
      <div className="inline-editor__fields">
        <TextField label="Name" value={form.label} onChange={(v) => set("label", v)} error={err("label")} />
        <SelectField
          label="Responsible"
          value={form.responsible}
          options={[{ value: "", label: "None" }, ...options]}
          onChange={(v) => set("responsible", v)}
        />
        {contested ? (
          <p className="field__help">
            Accountable: several roles (contested). Use the full edit form to choose between them.
          </p>
        ) : (
          <SelectField
            label="Accountable"
            value={form.accountable[0] ?? ""}
            options={[{ value: "", label: "Choose a role" }, ...options]}
            onChange={(v) => set("accountable", v ? [v] : [])}
          />
        )}
        <TextField label="Work (minutes)" mono value={form.work_min} onChange={(v) => set("work_min", v)} error={err("work_min")} />
        <TextField label="Wait (minutes)" mono value={form.wait_min} onChange={(v) => set("wait_min", v)} error={err("wait_min")} />
        <TextField label="KPI" value={form.kpi} onChange={(v) => set("kpi", v)} error={err("kpi")} />
      </div>
      {errors.raci && <p className="field__error">{errors.raci}</p>}
      {problem && (
        <p className="field__error" role="alert">
          {problem}
        </p>
      )}
      <div className="edit-form__actions">
        <Button variant="primary" type="submit">
          {saving ? "Saving…" : "Save"}
        </Button>
        <Button onClick={onCancel}>Cancel</Button>
        <button type="button" className="btn btn--link" onClick={onOpenFull}>
          Open the full edit form
        </button>
      </div>
    </form>
  );
}
