import { useState, type FormEvent } from "react";
import type { Engagement, ScopeFields } from "../../api/types";
import { Button, Card, CheckboxField, ChipField, TextAreaField, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useUpdateEngagement } from "../../hooks/useEngagements";
import { fieldOf, messageOf } from "../../lib/errors";
import { validateEngagementName, validateScopeList, validateScopeText } from "../../lib/validation";

type TextKey = "name" | "process_name" | "trigger" | "end_point" | "out_of_scope" | "process_kpi" | "industry";
type ListKey = "in_scope_roles" | "adjacent_industries" | "confidential_terms";
type FlagKey = "trigger_external" | "end_point_external";
type Form = Record<TextKey, string> & Record<ListKey, string[]> & Record<FlagKey, boolean>;

const LABELS: Record<TextKey | ListKey | FlagKey, string> = {
  trigger_external: "Starts outside the organisation",
  end_point_external: "Ends outside the organisation",
  name: "Engagement name",
  process_name: "Process name",
  trigger: "Trigger",
  end_point: "End point",
  in_scope_roles: "In-scope roles",
  out_of_scope: "Out of scope",
  process_kpi: "Process KPI",
  industry: "Industry",
  adjacent_industries: "Adjacent industries",
  confidential_terms: "Confidential terms",
};
const TEXT_KEYS: TextKey[] = ["name", "process_name", "trigger", "end_point", "out_of_scope", "process_kpi", "industry"];
const LIST_KEYS: ListKey[] = ["in_scope_roles", "adjacent_industries", "confidential_terms"];

function formOf(e: Engagement): Form {
  return {
    name: e.name,
    process_name: e.process_name,
    trigger: e.trigger,
    end_point: e.end_point,
    out_of_scope: e.out_of_scope,
    process_kpi: e.process_kpi,
    industry: e.industry,
    in_scope_roles: [...e.in_scope_roles],
    adjacent_industries: [...e.adjacent_industries],
    confidential_terms: [...e.confidential_terms],
    trigger_external: e.trigger_external ?? false,
    end_point_external: e.end_point_external ?? false,
  };
}

function validate(form: Form): Partial<Record<keyof Form, string>> {
  const errors: Partial<Record<keyof Form, string>> = {};
  const name = validateEngagementName(form.name);
  if (name) errors.name = name;
  for (const key of TEXT_KEYS.filter((k) => k !== "name")) {
    const problem = validateScopeText(LABELS[key], form[key]);
    if (problem) errors[key] = problem;
  }
  for (const key of LIST_KEYS) {
    const problem = validateScopeList(LABELS[key], form[key]);
    if (problem) errors[key] = problem;
  }
  return errors;
}

/** Process scope (PRD §5.4 Setup): what the map covers, plus terms never sent to web research. */
// 2026-10-28 (Eric's cargo manual describes import, export and transhipment on one page).
const SEVERAL_FLOWS =
  "One engagement maps one flow, from its trigger to its end point. If a document covers several flows (for example import, export and transhipment), make one engagement for each and upload the same document to each.";

export function ScopeCard({ engagement }: { engagement: Engagement }) {
  const [form, setForm] = useState<Form>(() => formOf(engagement));
  const [errors, setErrors] = useState<Partial<Record<keyof Form, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const save = useUpdateEngagement(engagement.id);
  const toast = useToast();

  const set = <K extends keyof Form>(key: K) => (value: Form[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  };

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const problems = validate(form);
    setErrors(problems);
    setFormError(null);
    if (Object.keys(problems).length > 0 || save.isPending) return;
    const fields: ScopeFields = { ...form };
    save.mutate(fields, {
      onSuccess: (saved) => {
        setForm(formOf(saved));
        toast("Scope saved.");
      },
      onError: (e) => {
        const field = fieldOf(e);
        if (field && field in LABELS) setErrors({ [field]: messageOf(e) });
        else setFormError(messageOf(e));
      },
    });
  }

  const text = (key: TextKey, help?: string) => (
    <TextField label={LABELS[key]} value={form[key]} onChange={set(key)} error={errors[key] ?? null} help={help} />
  );
  const list = (key: ListKey, help: string) => (
    <ChipField label={LABELS[key]} values={form[key]} onChange={set(key)} error={errors[key] ?? null} help={help} />
  );

  return (
    <Card title="Process scope" description="What this map covers. Claude uses it to stay inside the process.">
      <form className="setup-form" onSubmit={onSubmit} noValidate>
        {text("name")}
        {text("process_name", "The process as your organisation names it, if different.")}
        <div className="setup-form__pair">
          {text("trigger", "What starts the process.")}
          {text("end_point", "What marks it as finished.")}
        </div>
        <p className="setup-form__note">{SEVERAL_FLOWS}</p>
        <div className="setup-form__pair">
          <CheckboxField
            label={LABELS.trigger_external}
            checked={form.trigger_external}
            onChange={set("trigger_external")}
            error={errors.trigger_external ?? null}
            help="Tick when what starts the process comes from outside, for example a customer's request."
          />
          <CheckboxField
            label={LABELS.end_point_external}
            checked={form.end_point_external}
            onChange={set("end_point_external")}
            error={errors.end_point_external ?? null}
            help="Tick when it ends with a handover outside, for example to a customer or an authority. The Typical case view then shows a lane for it."
          />
        </div>
        {list("in_scope_roles", "Roles whose work this map covers.")}
        <TextAreaField
          label={LABELS.out_of_scope}
          value={form.out_of_scope}
          onChange={set("out_of_scope")}
          error={errors.out_of_scope ?? null}
          help="Related work this map leaves out."
        />
        {text("process_kpi", "How the process is measured, for example a time or error rate.")}
        <div className="setup-form__pair">
          {text("industry")}
          {list("adjacent_industries", "Used only by the optional external best-practice analysis.")}
        </div>
        {list(
          "confidential_terms",
          "Company, client, site and system names that must never be sent to web research. They stay visible inside the app.",
        )}
        {formError && (
          <p className="field__error" role="alert">
            {formError}
          </p>
        )}
        <div className="setup-form__actions">
          <Button variant="primary" type="submit">
            {save.isPending ? "Saving…" : "Save scope"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
