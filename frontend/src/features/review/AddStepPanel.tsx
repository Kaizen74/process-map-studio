import { useEffect, useState } from "react";
import { Button, ErrorState, Skeleton } from "../../components/common";
import { AddStepForm, SourceChoices, SourceViewer } from "../../components/panel";
import { useAddStep } from "../../hooks/useReview";
import { useSegments, useSource, useSources } from "../../hooks/useSources";
import {
  newStepBody,
  placesAfter,
  validateNewStep,
  type AddStepForm as Form,
  type PickedPassage,
} from "../../lib/addStep";
import { copyDetailsOf, fieldOf, messageOf } from "../../lib/errors";
import { isTyping } from "../../lib/keys";
import type { Graph } from "../../lib/mapTypes";
import { SOURCE_KINDS } from "../../lib/panelText";

export interface AddStepPanelProps {
  graph: Graph;
  initial: Form;
  versionId: string;
  engagementId: string;
  onAdded: (elementId: string) => void;
  onCancel: () => void;
}

type View = { kind: "form" } | { kind: "sources" } | { kind: "passages"; sourceId: string };

/** Add missing step in the panel (PRD §5.7.6), with the passage picker (PRD §5.7.8 pick mode). */
export function AddStepPanel({ graph, initial, versionId, engagementId, onAdded, onCancel }: AddStepPanelProps) {
  const [form, setForm] = useState(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState(false);
  const [view, setView] = useState<View>({ kind: "form" });
  const add = useAddStep(versionId, engagementId);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape" || isTyping(event.target)) return;
      if (view.kind === "form") onCancel(); // Esc discards the new step
      else setView({ kind: "form" }); // …or leaves the picker
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [view.kind, onCancel]);

  function change(next: Form) {
    setForm(next);
    if (checked) setErrors(validateNewStep(next));
  }

  function submit() {
    if (add.isPending) return;
    setChecked(true);
    const found = validateNewStep(form);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    add.mutate(newStepBody(form), {
      onSuccess: (detail) => onAdded(detail.id),
      onError: (error) => {
        const field = fieldOf(error);
        if (field) setErrors({ [field]: messageOf(error) });
      },
    });
  }

  if (view.kind === "sources") {
    return (
      <PickSource
        engagementId={engagementId}
        onChoose={(sourceId) => setView({ kind: "passages", sourceId })}
        onBack={() => setView({ kind: "form" })}
      />
    );
  }
  if (view.kind === "passages") {
    return (
      <PickPassage
        sourceId={view.sourceId}
        pickedIds={form.passages.map((p) => p.id)}
        onPick={(passage) => {
          change({ ...form, passages: [...form.passages, passage] });
          setView({ kind: "form" });
        }}
        onBack={() => setView({ kind: "sources" })}
      />
    );
  }
  const fieldError = add.error != null && fieldOf(add.error) !== undefined;
  return (
    <div className="panel-stack">
      <AddStepForm
        form={form}
        errors={errors}
        roles={graph.roles}
        places={placesAfter(graph)}
        saving={add.isPending}
        problem={add.error != null && !fieldError ? messageOf(add.error) : null}
        onChange={change}
        onPickPassage={() => setView({ kind: "sources" })}
        onSave={submit}
        onCancel={onCancel}
      />
    </div>
  );
}

function PickSource({
  engagementId,
  onChoose,
  onBack,
}: {
  engagementId: string;
  onChoose: (id: string) => void;
  onBack: () => void;
}) {
  const sources = useSources(engagementId);
  if (sources.isError) {
    return (
      <ErrorState
        title="The sources couldn't be loaded"
        message={messageOf(sources.error)}
        details={copyDetailsOf(sources.error)}
        onRetry={() => void sources.refetch()}
      />
    );
  }
  if (!sources.data) return <Skeleton height="160px" />;
  const readable = sources.data
    .filter((s) => s.text_status === "ready" && s.segment_count > 0)
    .map((s) => ({ id: s.id, name: s.filename, kind: SOURCE_KINDS[s.kind] ?? "Document", passages: s.segment_count }));
  return <SourceChoices sources={readable} backLabel="the new step" onChoose={onChoose} onBack={onBack} />;
}

function PickPassage({
  sourceId,
  pickedIds,
  onPick,
  onBack,
}: {
  sourceId: string;
  pickedIds: readonly string[];
  onPick: (passage: PickedPassage) => void;
  onBack: () => void;
}) {
  const source = useSource(sourceId);
  const pages = useSegments(sourceId);
  const failed = source.isError ? source : pages.isError ? pages : null;
  if (failed) {
    return (
      <ErrorState
        title="This source couldn't be opened"
        message={messageOf(failed.error)}
        details={copyDetailsOf(failed.error)}
        onRetry={() => void failed.refetch()}
      />
    );
  }
  if (!pages.data || !source.data) return <Skeleton height="240px" />;
  const s = source.data;
  const name = s.filename;
  const meta = [s.format, s.version_date && `version ${s.version_date}`, s.controlled_copy && "controlled copy"]
    .filter(Boolean)
    .join(" · ");
  const passages = pages.data.pages.flatMap((p) => p.segments);
  return (
    <SourceViewer
      kind={SOURCE_KINDS[s.kind] ?? "Document"}
      name={name}
      meta={meta}
      passages={passages}
      targetId=""
      quote=""
      backLabel="the list of sources"
      onBack={onBack}
      onPick={(p) => onPick({ id: p.id, anchor: p.anchor, source_name: name, text: p.text })}
      pickedIds={pickedIds}
      footer={
        pages.hasNextPage ? (
          <Button onClick={() => void pages.fetchNextPage()}>
            {pages.isFetchingNextPage ? "Loading…" : "Show more passages"}
          </Button>
        ) : null
      }
    />
  );
}
