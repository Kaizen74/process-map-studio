import { useEffect, useState } from "react";
import { Button } from "../../components/common";
import { InlineEditor, StepTable } from "../../components/table";
import { useEditStep } from "../../hooks/useReview";
import { fieldOf, messageOf } from "../../lib/errors";
import { isTyping } from "../../lib/keys";
import type { Graph } from "../../lib/mapTypes";
import { changedFields, formFrom, type StepForm } from "../../lib/stepForm";
import { filterOptions, tableRows, type TableFilter } from "../../lib/table";
import { validateStep } from "../../lib/validation";

export interface TableViewProps {
  graph: Graph;
  versionId: string;
  engagementId: string;
  selectedId: string | null;
  editable: boolean;
  onSelect: (id: string) => void;
  /** After a save the server accepted (auto-advance, as after Save edits). */
  onSaved: (id: string) => void;
  onOpenFullEdit: (id: string) => void;
  onAddStep: () => void;
}

/** The fields edited in place; a message about any other field sends Eric to the full form. */
const INLINE = new Set(["label", "work_min", "wait_min", "kpi", "raci"]);

/** The table view (PRD §5.7.4) with its filters and in-place editing. */
export function TableView({
  graph,
  versionId,
  engagementId,
  selectedId,
  editable,
  onSelect,
  onSaved,
  onOpenFullEdit,
  onAddStep,
}: TableViewProps) {
  const [filter, setFilter] = useState<TableFilter>("all");
  const [editing, setEditing] = useState<{ id: string; original: StepForm; form: StepForm } | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [problem, setProblem] = useState<string | null>(null);
  const save = useEditStep(versionId, engagementId);

  useEffect(() => {
    if (!editing) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !isTyping(event.target)) setEditing(null); // Esc discards
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editing]);

  function start(id: string) {
    const element = graph.elements.find((e) => e.id === id);
    if (!element) return;
    const form = formFrom(element);
    save.reset();
    setErrors({});
    setProblem(null);
    setEditing({ id, original: form, form });
    onSelect(id);
  }

  function submit() {
    if (!editing || save.isPending) return;
    const found = validateStep(editing.form, editing.original);
    const here = Object.fromEntries(Object.entries(found).filter(([key]) => INLINE.has(key)));
    const elsewhere = Object.entries(found).find(([key]) => !INLINE.has(key));
    setErrors(here);
    setProblem(elsewhere ? `${elsewhere[1]} Open the full edit form to fix it.` : null);
    if (Object.keys(found).length > 0) return;
    const patch = changedFields(editing.original, editing.form);
    const id = editing.id;
    if (Object.keys(patch).length === 0) {
      setEditing(null);
      return;
    }
    save.mutate(
      { elementId: id, patch },
      {
        onSuccess: () => {
          setEditing(null);
          onSaved(id);
        },
        onError: (error) => {
          const field = fieldOf(error);
          if (field && INLINE.has(field)) setErrors({ [field]: messageOf(error) });
          else setProblem(messageOf(error));
        },
      },
    );
  }

  const label = graph.elements.find((e) => e.id === editing?.id)?.label ?? "";
  return (
    <div className="table-view">
      {editable && (
        <div className="table-view__actions">
          <Button onClick={onAddStep}>Add missing step</Button>
        </div>
      )}
      <StepTable
        rows={tableRows(graph, filter)}
        filter={filter}
        filters={filterOptions(graph)}
        onFilter={setFilter}
        selectedId={selectedId}
        onSelect={onSelect}
        editingId={editing?.id ?? null}
        onEditInline={editable ? start : undefined}
        editor={
          editing && (
            <InlineEditor
              label={label}
              form={editing.form}
              errors={errors}
              roles={graph.roles}
              saving={save.isPending}
              problem={problem}
              onChange={(form) => {
                setEditing({ ...editing, form });
                if (Object.keys(errors).length > 0) {
                  const found = validateStep(form, editing.original);
                  setErrors(Object.fromEntries(Object.entries(found).filter(([key]) => INLINE.has(key))));
                }
              }}
              onSave={submit}
              onCancel={() => setEditing(null)}
              onOpenFull={() => {
                const id = editing.id;
                setEditing(null);
                onOpenFullEdit(id);
              }}
            />
          )
        }
      />
    </div>
  );
}
