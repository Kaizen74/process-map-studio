import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import type { AnotherFlow, Engagement } from "../../api/types";
import {
  Button,
  Card,
  Dialog,
  TextAreaField,
  TextField,
} from "../../components/common";
import { useToast } from "../../components/shell";
import { useAnotherFlow } from "../../hooks/useEngagements";
import { fieldOf, messageOf } from "../../lib/errors";
import { validateEngagementName } from "../../lib/validation";

const EMPTY: AnotherFlow = {
  name: "",
  trigger: "",
  end_point: "",
  out_of_scope: "",
};
const LABELS: Record<keyof AnotherFlow, string> = {
  name: "Engagement name",
  trigger: "Trigger",
  end_point: "End point",
  out_of_scope: "Out of scope",
};

/**
 * Map another flow from these sources (2026-10-28, DECISIONS 81): one engagement maps one flow,
 * so the next flow in the same documents starts a new engagement with the documents as already
 * read, the roles and the names to hide. Nothing of this map is copied.
 */
export function AnotherFlowCard({ engagement }: { engagement: Engagement }) {
  const start = useAnotherFlow(engagement.id);
  const navigate = useNavigate();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<AnotherFlow>(EMPTY);
  const [errors, setErrors] = useState<
    Partial<Record<keyof AnotherFlow, string>>
  >({});
  const [formError, setFormError] = useState<string | null>(null);

  const set = (key: keyof AnotherFlow) => (value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  };

  function close() {
    setOpen(false);
    setForm(EMPTY);
    setErrors({});
    setFormError(null);
  }

  function onSubmit(event?: FormEvent) {
    event?.preventDefault();
    const name = validateEngagementName(form.name);
    if (name) {
      setErrors({ name });
      return;
    }
    if (start.isPending) return;
    start.mutate(form, {
      onSuccess: (made) => {
        close();
        toast(
          `Started ${made.name} with the same documents, roles and names to hide. Check its scope, then draft it.`,
        );
        void navigate(`/engagements/${encodeURIComponent(made.id)}/setup`);
        // The new engagement's Setup opens at its heading (the top bar shows its name), not at
        // this button, where the dialog would otherwise return focus.
        window.setTimeout(() => {
          const heading = document.getElementById("setup-title");
          if (heading) {
            heading.tabIndex = -1;
            heading.focus();
          }
        }, 0);
      },
      onError: (e) => {
        const field = fieldOf(e);
        if (field && field in LABELS) setErrors({ [field]: messageOf(e) });
        else setFormError(messageOf(e));
      },
    });
  }

  return (
    <Card
      title="Another flow in these documents"
      description="Each flow is drafted, reviewed and published on its own. Start the next one here: it gets these documents (already read), roles and names to hide."
    >
      <div>
        <Button onClick={() => setOpen(true)}>
          Map another flow from these sources…
        </Button>
      </div>
      <Dialog
        open={open}
        title="Map another flow"
        description={`A new engagement with the documents, roles and names to hide of ${engagement.name}. This engagement stays as it is.`}
        onClose={close}
        actions={
          <>
            <Button onClick={close}>Cancel</Button>
            <Button variant="primary" onClick={() => onSubmit()}>
              {start.isPending ? "Starting…" : "Start this flow"}
            </Button>
          </>
        }
      >
        <form className="setup-form" onSubmit={onSubmit} noValidate>
          <TextField
            label={LABELS.name}
            value={form.name}
            onChange={set("name")}
            error={errors.name ?? null}
            help="For example Export or Transhipment."
          />
          <TextField
            label={LABELS.trigger}
            value={form.trigger}
            onChange={set("trigger")}
            error={errors.trigger ?? null}
            help="What starts this flow."
          />
          <TextField
            label={LABELS.end_point}
            value={form.end_point}
            onChange={set("end_point")}
            error={errors.end_point ?? null}
            help="What marks it as finished."
          />
          <TextAreaField
            label={LABELS.out_of_scope}
            value={form.out_of_scope}
            onChange={set("out_of_scope")}
            error={errors.out_of_scope ?? null}
            help="Other flows in the documents this map leaves out."
          />
          {formError && (
            <p className="field__error" role="alert">
              {formError}
            </p>
          )}
        </form>
      </Dialog>
    </Card>
  );
}
