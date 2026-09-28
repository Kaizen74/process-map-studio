import { useNavigate } from "react-router";
import { Button, Dialog } from "../../components/common";
import { useStartRefresh } from "../../hooks/useDraft";
import { engagementPath } from "../../lib/engagementSteps";
import { messageOf } from "../../lib/errors";
import { plural } from "../../lib/format";

export interface RefreshDialogProps {
  open: boolean;
  engagementId: string;
  versionId: string;
  versionLabel: string;
  /** Steps confirmed, edited, added or rejected: they stay exactly as they are. */
  kept: number;
  onClose: () => void;
}

/**
 * Refresh draft from sources (PRD §3.5, constraint 8): says what stays and what is redrafted,
 * starts the run and opens the Draft screen, where its progress shows.
 */
export function RefreshDialog({ open, engagementId, versionId, versionLabel, kept, onClose }: RefreshDialogProps) {
  const refresh = useStartRefresh(engagementId);
  const navigate = useNavigate();
  const close = () => {
    refresh.reset();
    onClose();
  };
  return (
    <Dialog
      open={open}
      title="Refresh draft from sources"
      description={`Claude reads every source again, for example after you added one, and redrafts the steps you haven't reviewed. The draft ${versionLabel} then gets the next number.`}
      actions={
        <>
          <Button onClick={close}>Cancel</Button>
          <Button
            variant="primary"
            onClick={() =>
              refresh.mutate(versionId, { onSuccess: () => void navigate(engagementPath(engagementId, "draft")) })
            }
          >
            {refresh.isPending ? "Starting…" : "Refresh draft"}
          </Button>
        </>
      }
      onClose={close}
    >
      <ul className="how-to">
        <li>
          {kept === 0
            ? "You haven't reviewed any steps yet, so every step is drafted again."
            : `The ${plural(kept, "step")} you confirmed, edited, added or rejected stay exactly as they are.`}
        </li>
        <li>Validation questions you marked answered stay answered when Claude asks them again.</li>
        <li>It uses AI calls and takes a few minutes. You can follow it on the Draft screen.</li>
      </ul>
      {refresh.error != null && (
        <p className="field__error" role="alert">
          {messageOf(refresh.error)}
        </p>
      )}
    </Dialog>
  );
}
