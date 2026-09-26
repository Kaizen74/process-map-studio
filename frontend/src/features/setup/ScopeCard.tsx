import { useState, type FormEvent } from "react";
import type { Engagement, ScopeFields } from "../../api/types";
import { Button, Card, ChipField, TextAreaField, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useUpdateEngagement } from "../../hooks/useEngagements";
import { fieldOf, messageOf } from "../../lib/errors";
import { validateEngagementName, validateScopeList, validateScopeText } from "../../lib/validation";

type TextKey = "name" | "process_name" | "trigger" | "end_point" | "out_of_scope" | "process_kpi" | "industry";
type ListKey = "in_scope_roles" | "adjacent_industries" | "confidential_terms";
type Form = Record<TextKey, string> & Record<ListKey, string[]>;

const LABELS: Record<TextKey | ListKey, string> = {
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
