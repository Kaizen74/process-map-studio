import { useState, type FormEvent } from "react";
import { GUARDRAIL_LABELS, type GapFinding, type GapStepChoice } from "../../lib/gap";
import { Button, SelectField, TextAreaField, TextField } from "../common";
import "../registers/registers.css";
import "../tabs/tabs.css";
import "./gap.css";

export interface GapStepFormProps {
  finding: GapFinding;
  /** Lanes of the draft the step goes into. */
  roles: readonly { id: string; name: string }[];
  /** Where the new step can go, in process order. */
  places: readonly { value: string; label: string }[];
  saving: boolean;
  problem: string | null;
  onSave: (step: GapStepChoice) => void;
  onCancel: () => void;
}

const KINDS = [
  { value: "activity", label: "Activity" },
  { value: "decision", label: "Decision" },
  { value: "approval", label: "Approval" },
];
const MECHANISMS = [
  { value: "judgment", label: "Judgment call" },
  { value: "rule_based", label: "Follows a rule" },
];

/**
 * Add as step, pre-filled from the finding (PRD §3.11.3): Eric chooses the name, kind, lane and
 * where it goes. Where it comes from is taken from the finding: an external finding's source as
 * the reference (Recommended), or its passages (Observed).
 */
export function GapStepForm({ finding, roles, places, saving, problem, onSave, onCancel }: GapStepFormProps) {
  const [step, setStep] = useState<GapStepChoice>({
    kind: "activity",
    label: finding.title.slice(0, 120),
    lane_role_id: roles[0]?.id ?? "",
    after_element_id: places[0]?.value ?? "",
    mechanism: "judgment",
  });
  const [missing, setMissing] = useState<string | null>(null);
  const deciding = step.kind === "decision" || step.kind === "approval";
  const external = finding.evidence.some((e) => e.side === "external");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!step.label.trim()) return setMissing("Give the step a name.");
    if (!step.lane_role_id) return setMissing("Choose the lane (the role that does it).");
    if (!step.after_element_id) return setMissing("Choose where the new step goes.");
    setMissing(null);
    if (!saving) onSave({ ...step, label: step.label.trim() });
  }

  return (
    <form className="gap-form" onSubmit={submit} aria-label="Add as step">
      <p className="gap-form__intro">
        {external
          ? "The step is added to the draft as Recommended, with this finding's source as its reference."
          : "The step is added to the draft as Observed, on this finding's passages."}
      </p>
      <TextField label="Step name" value={step.label} onChange={(label) => setStep({ ...step, label })} />
      <SelectField
        label="Kind"
        value={step.kind}
        options={KINDS}
        onChange={(kind) => setStep({ ...step, kind: kind as GapStepChoice["kind"] })}
      />
      <SelectField
        label="Lane"
        value={step.lane_role_id}
        options={roles.map((r) => ({ value: r.id, label: r.name }))}
        onChange={(lane_role_id) => setStep({ ...step, lane_role_id })}
      />
      <SelectField
        label="Comes after"
        value={step.after_element_id}
        options={places}
        onChange={(after_element_id) => setStep({ ...step, after_element_id })}
      />
      {deciding && (
        <SelectField
          label="How is it decided?"
          value={step.mechanism}
          options={MECHANISMS}
          onChange={(mechanism) => setStep({ ...step, mechanism: mechanism as GapStepChoice["mechanism"] })}
        />
      )}
      {(missing ?? problem) && (
        <p className="gap-form__problem" role="alert">
          {missing ?? problem}
        </p>
      )}
      <div className="gap-form__actions">
        <Button variant="primary" type="submit" aria-busy={saving || undefined}>
          {saving ? "Adding…" : "Add step"}
        </Button>
        <Button onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}

export interface DismissFormProps {
  saving: boolean;
  problem: string | null;
  onDismiss: (reason: string) => void;
  onCancel: () => void;
}

/** Dismiss needs a reason (PRD §3.11.3); it is kept with the finding and in the export. */
export function DismissForm({ saving, problem, onDismiss, onCancel }: DismissFormProps) {
  const [reason, setReason] = useState("");
  const [missing, setMissing] = useState<string | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!reason.trim()) return setMissing("Say why you're dismissing this finding.");
    setMissing(null);
    if (!saving) onDismiss(reason.trim());
  }

  return (
    <form className="gap-form" onSubmit={submit} aria-label="Dismiss finding">
      <TextAreaField
        label="Why dismiss it?"
        value={reason}
        onChange={setReason}
        help="For example: the SOP is being rewritten, or the process owner checked it."
        error={missing}
      />
      {problem && (
        <p className="gap-form__problem" role="alert">
          {problem}
        </p>
      )}
      <div className="gap-form__actions">
        <Button variant="primary" type="submit" aria-busy={saving || undefined}>
          {saving ? "Dismissing…" : "Dismiss finding"}
        </Button>
        <Button onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}

/** Findings a guardrail or the independent check turned down, with the guardrail ID. */
export function RejectedFindings({ rejected }: { rejected: readonly GapFinding[] }) {
  if (rejected.length === 0) return null;
  return (
    <details className="rejected-findings">
      <summary>
        Rejected findings ({rejected.length}): kept here for transparency, never used
      </summary>
      <ul className="tab-cards">
        {rejected.map((f) => (
          <li key={f.id} className="register-card">
            <p className="register-card__title">{f.title}</p>
            <p className="register-card__meta">
              <span className="mono">{f.rejection_guardrail}</span> ·{" "}
              {GUARDRAIL_LABELS[f.rejection_guardrail] ?? f.rejection_guardrail}: {f.rejection_reason}
            </p>
          </li>
        ))}
      </ul>
    </details>
  );
}
