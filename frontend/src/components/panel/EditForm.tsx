import type { FormEvent } from "react";
import type { StepErrors } from "../../lib/validation";
import {
  AI_BASES,
  AI_COMPONENTS,
  CAUSE_TYPES,
  KINDS,
  MECHANISMS,
  type AiFlagFields,
  type ConstraintRow,
  type StepForm,
} from "../../lib/stepForm";
import { Button, CheckboxField, SelectField, TextAreaField, TextField } from "../common";

export interface EditFormProps {
  form: StepForm;
  errors: StepErrors;
  roles: readonly { id: string; name: string }[];
  saving: boolean;
  /** A problem that isn't about one field (e.g. the version can't change). */
  problem: string | null;
  onChange: (form: StepForm) => void;
  onSave: () => void;
  onCancel: () => void;
}

function RoleChecks({
  legend,
  roles,
  chosen,
  onChange,
}: {
  legend: string;
  roles: readonly { id: string; name: string }[];
  chosen: readonly string[];
  onChange: (ids: string[]) => void;
}) {
  return (
    <fieldset className="edit-roles">
      <legend className="field__label">{legend}</legend>
      {roles.map((role) => (
        <CheckboxField
          key={role.id}
          label={role.name}
          checked={chosen.includes(role.id)}
          onChange={(on) => onChange(on ? [...chosen, role.id] : chosen.filter((id) => id !== role.id))}
        />
      ))}
    </fieldset>
  );
}

const NEW_FLAG: AiFlagFields = {
  component: "perception",
  input: "",
  output: "",
  handoff: "",
  basis: "judgment_support_only",
};
const NEW_CONSTRAINT: ConstraintRow = { text: "", cause_type: "", is_key: false, provenance: "O" };

/**
 * The edit form (PRD §5.7.6). Required: the name, an Accountable role, and a Responsible role for
 * an activity. A field that fails its rule gets a coral border and the message right below;
 * Save edits explains instead of saving until everything passes.
 */
export function EditForm({ form, errors, roles, saving, problem, onChange, onSave, onCancel }: EditFormProps) {
  const set = <K extends keyof StepForm>(key: K, value: StepForm[K]) => onChange({ ...form, [key]: value });
  const roleOptions = roles.map((r) => ({ value: r.id, label: r.name }));
  const deciding = form.kind === "decision" || form.kind === "approval";
  const count = Object.keys(errors).length;
  const err = (key: string) => errors[key] ?? null;

  function submit(event: FormEvent) {
    event.preventDefault();
    onSave();
  }

  function setConstraint(index: number, change: Partial<ConstraintRow>) {
    set(
      "constraints",
      form.constraints.map((c, i) => (i === index ? { ...c, ...change } : c)),
    );
  }

  return (
    <form className="edit-form" aria-label="Edit step" onSubmit={submit} noValidate>
      <TextField label="Name" value={form.label} onChange={(v) => set("label", v)} error={err("label")} />
      <div className="edit-form__pair">
        <SelectField label="Kind" value={form.kind} options={KINDS} onChange={(v) => set("kind", v)} error={err("kind")} />
        <SelectField
          label="Lane"
          value={form.lane_role_id}
          options={[{ value: "", label: "Choose a role" }, ...roleOptions]}
          onChange={(v) => set("lane_role_id", v)}
          error={err("lane_role_id")}
        />
      </div>

      <section className="edit-form__group" aria-label="Role and accountability">
        <h3 className="panel-section__title">Role and accountability</h3>
        <SelectField
          label="Responsible"
          value={form.responsible}
          options={[{ value: "", label: "None" }, ...roleOptions]}
          onChange={(v) => set("responsible", v)}
        />
        <RoleChecks legend="Accountable" roles={roles} chosen={form.accountable} onChange={(v) => set("accountable", v)} />
        {form.accountable.length > 1 && (
          <p className="field__help">Several Accountable roles are marked contested (A?): the sources disagree.</p>
        )}
        <RoleChecks legend="Consulted" roles={roles} chosen={form.consulted} onChange={(v) => set("consulted", v)} />
        <RoleChecks legend="Informed" roles={roles} chosen={form.informed} onChange={(v) => set("informed", v)} />
        {errors.raci && <p className="field__error">{errors.raci}</p>}
      </section>

      <section className="edit-form__group" aria-label="Time">
        <h3 className="panel-section__title">Time</h3>
        <div className="edit-form__pair">
          <TextField label="Work (minutes)" mono value={form.work_min} onChange={(v) => set("work_min", v)} error={err("work_min")} />
          <TextField label="Wait (minutes)" mono value={form.wait_min} onChange={(v) => set("wait_min", v)} error={err("wait_min")} />
        </div>
        <TextField label="Time window" value={form.duration_text} onChange={(v) => set("duration_text", v)} error={err("duration_text")} />
        <SelectField
          label="Complexity"
          value={form.complexity}
          options={[
            { value: "", label: "Not stated" },
            { value: "L", label: "Low (L)" },
            { value: "M", label: "Medium (M)" },
            { value: "H", label: "High (H)" },
          ]}
          onChange={(v) => set("complexity", v)}
        />
      </section>

      <TextField label="KPI" value={form.kpi} onChange={(v) => set("kpi", v)} error={err("kpi")} />

      {(deciding || form.mechanism !== "none") && (
        <section className="edit-form__group" aria-label="Decision rights and mechanism">
          <h3 className="panel-section__title">Decision rights and mechanism</h3>
          <SelectField
            label="Mechanism"
            value={form.mechanism}
            options={MECHANISMS}
            onChange={(v) => set("mechanism", v)}
            error={err("decision.mechanism")}
          />
          <SelectField
            label="Decider"
            value={form.decider_role_id}
            options={[{ value: "", label: "Not stated" }, ...roleOptions]}
            onChange={(v) => set("decider_role_id", v)}
          />
          <TextField
            label="Rule or threshold"
            value={form.rule_or_threshold}
            onChange={(v) => set("rule_or_threshold", v)}
            error={err("decision.rule_or_threshold")}
          />
          <TextField label="Escalation" value={form.escalation} onChange={(v) => set("escalation", v)} error={err("decision.escalation")} />
        </section>
      )}

      <div className="edit-form__pair">
        <TextField label="Handoff in" value={form.handoff_in} onChange={(v) => set("handoff_in", v)} error={err("handoff.in")} />
        <TextField label="Handoff out" value={form.handoff_out} onChange={(v) => set("handoff_out", v)} error={err("handoff.out")} />
      </div>

      <section className="edit-form__group" aria-label="Key challenges and constraints">
        <h3 className="panel-section__title">Key challenges and constraints</h3>
        {form.constraints.map((c, i) => (
          <div key={i} className="edit-form__constraint">
            <TextField label={`Constraint ${i + 1}`} value={c.text} onChange={(v) => setConstraint(i, { text: v })} />
            <SelectField
              label="Cause type"
              value={c.cause_type}
              options={CAUSE_TYPES}
              onChange={(v) => setConstraint(i, { cause_type: v })}
            />
            <CheckboxField label="Key constraint" checked={c.is_key} onChange={(v) => setConstraint(i, { is_key: v })} />
            <button
              type="button"
              className="btn btn--link"
              onClick={() => set("constraints", form.constraints.filter((_, j) => j !== i))}
            >
              Remove constraint {i + 1}
            </button>
          </div>
        ))}
        {errors.constraints && <p className="field__error">{errors.constraints}</p>}
        <Button onClick={() => set("constraints", [...form.constraints, NEW_CONSTRAINT])}>Add constraint</Button>
      </section>

      <TextAreaField label="Knowledge risk" value={form.k_risk} onChange={(v) => set("k_risk", v)} error={err("k_risk")} rows={2} />

      <section className="edit-form__group" aria-label="AI flag">
        <h3 className="panel-section__title">AI flag</h3>
        <CheckboxField
          label="This step has an AI flag"
          checked={form.ai_flag !== null}
          onChange={(on) => set("ai_flag", on ? { ...NEW_FLAG } : null)}
        />
        {form.ai_flag && (
          <>
            <SelectField
              label="Component"
              value={form.ai_flag.component}
              options={AI_COMPONENTS}
              onChange={(v) => form.ai_flag && set("ai_flag", { ...form.ai_flag, component: v })}
            />
            {(["input", "output", "handoff"] as const).map((key) => (
              <TextField
                key={key}
                label={key.charAt(0).toUpperCase() + key.slice(1)}
                value={form.ai_flag?.[key] ?? ""}
                onChange={(v) => form.ai_flag && set("ai_flag", { ...form.ai_flag, [key]: v })}
                error={err(`ai_flag.${key}`)}
              />
            ))}
            <SelectField
              label="Basis"
              value={form.ai_flag.basis}
              options={AI_BASES}
              onChange={(v) => form.ai_flag && set("ai_flag", { ...form.ai_flag, basis: v })}
              error={err("ai_flag.basis")}
            />
          </>
        )}
      </section>

      {problem && (
        <p className="field__error" role="alert">
          {problem}
        </p>
      )}
      {count > 0 && (
        <p className="field__error" role="alert">
          {count === 1 ? "One field needs attention" : `${count} fields need attention`} before these edits can be saved.
        </p>
      )}
      <div className="edit-form__actions">
        <Button variant="primary" type="submit">
          {saving ? "Saving…" : "Save edits"}
        </Button>
        <Button onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}
