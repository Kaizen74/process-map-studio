import { useState } from "react";
import type { ModelSummary, Settings } from "../../api/types";
import { Button, Card, CheckboxField, ErrorState, SelectField, Skeleton } from "../../components/common";
import { useToast } from "../../components/shell";
import { useModelChoices, useSaveModel } from "../../hooks/useSettings";
import { copyDetailsOf, messageOf } from "../../lib/errors";

const EFFORT_LABELS: Record<string, string> = {
  low: "Low",
  medium: "Medium",
  high: "High (recommended)",
  xhigh: "Extra high",
  max: "Max",
};
const ALL_EFFORTS = ["low", "medium", "high", "xhigh", "max"];

function effortsFor(model: ModelSummary | undefined): string[] {
  return model && model.effort_levels.length > 0 ? model.effort_levels : ALL_EFFORTS;
}

/** Model, effort and verifier (PRD §5.4 Settings). */
export function ModelCard({ settings }: { settings: Settings }) {
  const choices = useModelChoices(true);
  const save = useSaveModel();
  const toast = useToast();
  const [model, setModel] = useState(settings.model);
  const [effort, setEffort] = useState(settings.effort);
  const [verifier, setVerifier] = useState(settings.verifier_enabled);
  const [error, setError] = useState<string | null>(null);

  const models = choices.data?.models ?? [];
  const efforts = effortsFor(models.find((m) => m.id === model));

  function onModelChange(next: string) {
    setModel(next);
    const allowed = effortsFor(models.find((m) => m.id === next));
    if (!allowed.includes(effort)) setEffort(allowed.includes("high") ? "high" : (allowed.at(-1) ?? "high"));
  }

  function onSave() {
    setError(null);
    save.mutate(
      { model, effort, verifier_enabled: verifier },
      { onSuccess: () => toast("Model settings saved."), onError: (e) => setError(messageOf(e)) },
    );
  }

  return (
    <Card title="Model" description="Which Claude model drafts and checks your maps.">
      <div className="settings-form">
        {choices.isPending && (
          <div className="stack" aria-busy="true">
            <Skeleton height="28px" />
            <Skeleton height="28px" />
          </div>
        )}
        {choices.isError && (
          <ErrorState
            title="The model list couldn't be loaded"
            message={messageOf(choices.error)}
            details={copyDetailsOf(choices.error)}
            onRetry={() => void choices.refetch()}
          />
        )}
        {choices.isSuccess && (
          <>
            {choices.data.message && <p className="inline-note">{choices.data.message}</p>}
            <SelectField
              label="Model"
              value={model}
              onChange={onModelChange}
              options={models.map((m) => ({
                value: m.id,
                label: m.display_name === m.id ? m.id : `${m.display_name} (${m.id})`,
              }))}
            />
            <SelectField
              label="Effort"
              value={effort}
              onChange={setEffort}
              options={efforts.map((level) => ({ value: level, label: EFFORT_LABELS[level] ?? level }))}
              help="How hard Claude thinks. Higher effort is slower and costs more."
            />
            <CheckboxField
              label="Independent verifier"
              checked={verifier}
              onChange={setVerifier}
              help="Checks every step a second time against only its evidence. Costs more; raises accuracy."
            />
            {!verifier && (
              <p className="danger-note">
                The verifier is off: confidence scores will be lower and more steps will need checking.
              </p>
            )}
            {error && <p className="field__error">{error}</p>}
            <div className="settings-actions">
              <Button variant="primary" onClick={onSave}>
                {save.isPending ? "Saving…" : "Save model settings"}
              </Button>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
