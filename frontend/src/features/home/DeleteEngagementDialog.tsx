import { useState } from "react";
import type { EngagementSummary } from "../../api/types";
import { Button, Dialog } from "../../components/common";
import { useToast } from "../../components/shell";
import { useDeleteEngagement } from "../../hooks/useEngagements";
import { messageOf } from "../../lib/errors";
import { plural } from "../../lib/format";

export interface DeleteEngagementDialogProps {
  engagement: EngagementSummary | null;
  onClose: () => void;
}

/** Destructive confirmation naming exactly what will be removed (PRD §5.3). */
export function DeleteEngagementDialog({ engagement, onClose }: DeleteEngagementDialogProps) {
  const remove = useDeleteEngagement();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);

  function close() {
    setError(null);
    onClose();
  }

  function onConfirm() {
    if (!engagement || remove.isPending) return;
    remove.mutate(engagement.id, {
      onSuccess: () => {
        toast("Engagement deleted.");
        close();
      },
      onError: (e) => setError(messageOf(e)),
    });
  }

  const sources = engagement ? plural(engagement.sources_count, "source file") : "";
  return (
    <Dialog
      open={engagement !== null}
      title={`Delete “${engagement?.name ?? ""}”?`}
      description={`This removes the engagement, its ${sources}, its roles, drafts and published versions, and every file stored for it on this computer. This can't be undone.`}
      onClose={close}
      actions={
        <>
          <Button onClick={close}>{error ? "Close" : "Cancel"}</Button>
          {!error && (
            <Button variant="danger" onClick={onConfirm}>
              {remove.isPending ? "Deleting…" : "Delete engagement"}
            </Button>
          )}
        </>
      }
    >
      {error && (
        <p className="field__error" role="alert">
          {error}
        </p>
      )}
    </Dialog>
  );
}
