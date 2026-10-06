import { useState } from "react";
import { DEFAULT_CONVENTIONS, type Engagement, type MappingConventions } from "../../api/types";
import { Button, Card, SegmentedControl } from "../../components/common";
import { useToast } from "../../components/shell";
import { useUpdateEngagement } from "../../hooks/useEngagements";
import { messageOf } from "../../lib/errors";

// Mapping conventions (PRD §5.4 Setup, Appendix E tier 2, criterion 58; C7a): how detailed the map
// is and how steps and phases are named. They take effect at the next draft or refresh.

const GRANULARITY = [
  { value: "coarse", label: "Coarse" },
  { value: "standard", label: "Standard" },
  { value: "fine", label: "Fine" },
] as const;
const LABEL_STYLE = [
  { value: "standard", label: "Standard wording" },
  { value: "sme", label: "SME wording" },
] as const;
const PHASE_NAMING = [
  { value: "sme", label: "SME terms" },
  { value: "standard", label: "Standard terms" },
] as const;

const STEPS: Record<MappingConventions["granularity"], string> = {
  coarse: "about 8–12 steps",
  standard: "about 12–20 steps",
  fine: "about 20–25 steps",
};

export function ConventionsCard({ engagement }: { engagement: Engagement }) {
  const saved = engagement.conventions ?? DEFAULT_CONVENTIONS;
  const [form, setForm] = useState<MappingConventions>(saved);
  const save = useUpdateEngagement(engagement.id);
  const toast = useToast();
  const changed =
    form.granularity !== saved.granularity || form.label_style !== saved.label_style || form.phase_naming !== saved.phase_naming;
  const refusal = save.error ? messageOf(save.error) : null;
  return (
    <Card title="Mapping conventions" description="How detailed the map is and how its steps and phases are named. Used from the next draft or refresh.">
      <form
        className="stack"
        aria-label="Mapping conventions"
        onSubmit={(event) => {
          event.preventDefault();
          if (save.isPending) return;
          save.mutate(
            { conventions: form },
            {
              onSuccess: (next) => {
                setForm(next.conventions ?? DEFAULT_CONVENTIONS);
                toast("Mapping conventions saved. They apply from the next draft or refresh.");
              },
            },
          );
        }}
      >
        <SegmentedControl
          label="Granularity"
          options={GRANULARITY}
          value={form.granularity}
          onChange={(granularity) => setForm({ ...form, granularity })}
        />
        <p className="field__help">{STEPS[form.granularity]}; steps are merged or split, never by dropping a handoff or a decision.</p>
        <SegmentedControl
          label="Step labels"
          options={LABEL_STYLE}
          value={form.label_style}
          onChange={(label_style) => setForm({ ...form, label_style })}
        />
        <p className="field__help">
          {form.label_style === "sme"
            ? "The interviewee's own everyday name for a step, where there is one (added to the glossary with a plain meaning)."
            : "Verb and object, at most five words."}
        </p>
        <SegmentedControl
          label="Phase names"
          options={PHASE_NAMING}
          value={form.phase_naming}
          onChange={(phase_naming) => setForm({ ...form, phase_naming })}
        />
        {refusal && (
          <p className="field__error" role="alert">
            {refusal}
          </p>
        )}
        <div>
          <Button type="submit" variant="primary" aria-busy={save.isPending}>
            {save.isPending ? "Saving…" : changed ? "Save conventions" : "Saved"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
