import { useEffect, useState } from "react";
import { EditForm, PanelHeader } from "../../components/panel";
import { ErrorState, Skeleton } from "../../components/common";
import { useEditStep, useElement } from "../../hooks/useReview";
import { copyDetailsOf, fieldOf, messageOf } from "../../lib/errors";
import { isTyping } from "../../lib/keys";
import type { GraphElement } from "../../lib/mapTypes";
import { changedFields, formFrom, type StepForm } from "../../lib/stepForm";
import { validateStep, type StepErrors } from "../../lib/validation";

export interface EditPanelProps {
  element: GraphElement;
  laneName: string;
  phaseName: string;
  roles: readonly { id: string; name: string }[];
  versionId: string;
  engagementId: string;
  /** After a save the server accepted (or a Save with nothing changed). */
  onSaved: () => void;
  onCancel: () => void;
}

/** The edit form in the panel (PRD §5.7.6): shared field rules first, then the server's. */
export function EditPanel(props: EditPanelProps) {
  const detail = useElement(props.element.id);
  if (detail.isError) {
    return (
      <div className="panel-stack">
        <ErrorState
          title="The step's details couldn't be loaded"
          message={messageOf(detail.error)}
          details={copyDetailsOf(detail.error)}
          onRetry={() => void detail.refetch()}
        />
        <button type="button" className="btn btn--link" onClick={props.onCancel}>
          Cancel
        </button>
      </div>
    );
  }
  if (!detail.data) {
    return (
      <div className="stack" aria-busy="true">
        <Skeleton height="48px" />
        <Skeleton height="320px" />
      </div>
    );
  }
  // Keyed so that a fresh element starts a fresh form.
  return <EditFormState key={detail.data.id} original={formFrom(detail.data)} {...props} />;
}

function EditFormState({
  element,
  laneName,
  phaseName,
  roles,
  versionId,
  engagementId,
  original,
  onSaved,
  onCancel,
}: EditPanelProps & { original: StepForm }) {
  const [form, setForm] = useState(original);
  const [errors, setErrors] = useState<StepErrors>({});
  const [checked, setChecked] = useState(false);
  const save = useEditStep(versionId, engagementId);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !isTyping(event.target)) onCancel(); // Esc discards
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  function change(next: StepForm) {
    setForm(next);
    // Once Save has been tried, messages follow the fields as they are corrected.
    if (checked) setErrors(validateStep(next, original));
  }

  function submit() {
    if (save.isPending) return;
    setChecked(true);
    const found = validateStep(form, original);
    setErrors(found);
    if (Object.keys(found).length > 0) return; // refused until every field passes
    const patch = changedFields(original, form);
    if (Object.keys(patch).length === 0) {
      onSaved();
      return;
    }
    save.mutate(
      { elementId: element.id, patch },
      {
        onSuccess: onSaved,
        onError: (error) => {
          const field = fieldOf(error);
          if (field) setErrors({ [field]: messageOf(error) });
        },
      },
    );
  }

  const fieldError = save.error != null && fieldOf(save.error) !== undefined;
  return (
    <div className="panel-stack">
      <PanelHeader element={element} laneName={laneName} phaseName={phaseName} />
      <EditForm
        form={form}
        errors={errors}
        roles={roles}
        saving={save.isPending}
        problem={save.error != null && !fieldError ? messageOf(save.error) : null}
        onChange={change}
        onSave={submit}
        onCancel={onCancel}
      />
    </div>
  );
}
