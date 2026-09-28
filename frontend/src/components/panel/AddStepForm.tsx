import type { FormEvent } from "react";
import {
  DECIDING_MECHANISMS,
  PROVENANCES,
  type AddProvenance,
  type AddStepForm as Form,
} from "../../lib/addStep";
import { KINDS } from "../../lib/stepForm";
import { Button, SegmentedControl, SelectField, TextAreaField, TextField } from "../common";

export interface AddStepFormProps {
  form: Form;
  errors: Record<string, string>;
  roles: readonly { id: string; name: string }[];
  /** Where the new step can go, in process order. */
  places: readonly { value: string; label: string }[];
  saving: boolean;
  problem: string | null;
  onChange: (form: Form) => void;
  onPickPassage: () => void;
  onSave: () => void;
  onCancel: () => void;
}

/**
 * Add missing step (PRD §5.7.6): name, kind, lane, where it goes and where it comes from. An
 * observed step needs a passage picked in a source; a recommended step needs a typed reference.
 */
export function AddStepForm({
  form,
  errors,
  roles,
  places,
  saving,
  problem,
  onChange,
  onPickPassage,
  onSave,
  onCancel,
}: AddStepFormProps) {
  const set = <K extends keyof Form>(key: K, value: Form[K]) => onChange({ ...form, [key]: value });
  const err = (key: string) => errors[key] ?? null;
  const deciding = form.kind === "decision" || form.kind === "approval";

  function submit(event: FormEvent) {
    event.preventDefault();
    onSave();
  }

  return (
    <form className="edit-form" aria-label="Add missing step" onSubmit={submit} noValidate>
      <h2 className="panel-viewer__title">Add missing step</h2>
      <p className="field__help">
        Your own step, not an AI claim. It is added as locked: refreshing the draft never changes it.
      </p>
      <TextField label="Name" value={form.label} onChange={(v) => set("label", v)} error={err("label")} />
      <div className="edit-form__pair">
        <SelectField label="Kind" value={form.kind} options={KINDS} onChange={(v) => set("kind", v)} error={err("kind")} />
        <SelectField
          label="Lane"
          value={form.lane_role_id}
          options={[{ value: "", label: "Choose a role" }, ...roles.map((r) => ({ value: r.id, label: r.name }))]}
          onChange={(v) => set("lane_role_id", v)}
          error={err("lane_role_id")}
        />
      </div>
      <SelectField
        label="Comes after"
        value={form.after_element_id}
        options={places}
        onChange={(v) => set("after_element_id", v)}
        error={err("after_element_id")}
      />
      {deciding && (
        <SelectField
          label="Mechanism"
          value={form.mechanism}
          options={DECIDING_MECHANISMS}
          onChange={(v) => set("mechanism", v)}
          error={err("mechanism")}
        />
      )}

      <section className="edit-form__group" aria-label="Where it comes from">
        <h3 className="panel-section__title">Where it comes from</h3>
        <SegmentedControl<AddProvenance>
          label="Where it comes from"
          options={PROVENANCES}
          value={form.provenance}
          onChange={(v) => set("provenance", v)}
        />
        {form.provenance === "O" ? (
          <>
            {form.passages.length > 0 && (
              <ul className="picked-passages" aria-label="Picked passages">
                {form.passages.map((p) => (
                  <li key={p.id} className="picked-passage">
                    <span className="mono picked-passage__anchor">
                      {p.source_name} · {p.anchor}
                    </span>
                    {p.text && <p className="picked-passage__text">{p.text}</p>}
                    <button
                      type="button"
                      className="btn btn--link"
                      onClick={() => set("passages", form.passages.filter((x) => x.id !== p.id))}
                    >
                      Remove {p.anchor}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <Button onClick={onPickPassage}>{form.passages.length ? "Pick another passage" : "Pick a passage"}</Button>
            {errors.segment_ids && <p className="field__error">{errors.segment_ids}</p>}
          </>
        ) : (
          <TextAreaField
            label="Reference"
            help="Title and link of the external practice this step comes from."
            value={form.r_reference}
            onChange={(v) => set("r_reference", v)}
            error={err("r_reference")}
            rows={2}
          />
        )}
      </section>

      {problem && (
        <p className="field__error" role="alert">
          {problem}
        </p>
      )}
      <div className="edit-form__actions">
        <Button variant="primary" type="submit">
          {saving ? "Adding…" : "Add step"}
        </Button>
        <Button onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}
