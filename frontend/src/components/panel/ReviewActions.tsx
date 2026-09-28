import { Button } from "../common";

export interface ReviewActionsProps {
  status: string;
  needsCheck: boolean;
  busy: boolean;
  onConfirm: () => void;
  onReject: () => void;
  onRestore: () => void;
  /** Opens the edit form; omitted where editing isn't available. */
  onEdit?: () => void;
}

const LOCKED: Readonly<Record<string, string>> = {
  confirmed: "Confirmed",
  edited: "Edited",
  added: "Added by you",
};

function Lock() {
  return (
    <svg className="review-strip__lock" width="12" height="14" viewBox="0 0 12 14" aria-hidden="true" focusable="false">
      <rect x="1" y="6" width="10" height="7" rx="1.5" />
      <path d="M3.5 6V4a2.5 2.5 0 0 1 5 0v2" fill="none" />
    </svg>
  );
}

/** The review state of the selected step and what can be done with it (PRD §5.7.5). */
export function ReviewActions({ status, needsCheck, busy, onConfirm, onReject, onRestore, onEdit }: ReviewActionsProps) {
  const locked = LOCKED[status];
  if (locked) {
    return (
      <div className="review-strip review-strip--locked" role="status">
        <Lock />
        <span>{locked} · locked against AI re-runs</span>
        {onEdit && (
          <button type="button" className="btn btn--link" onClick={onEdit}>
            Edit
          </button>
        )}
      </div>
    );
  }
  if (status === "rejected") {
    return (
      <div className="review-strip review-strip--rejected" role="status">
        <span>Rejected. Its connected steps may now be orphaned; the map checks show what to fix.</span>
        <Button onClick={onRestore}>{busy ? "Restoring…" : "Restore"}</Button>
      </div>
    );
  }
  return (
    <div className="review-well">
      <p className="review-well__note">
        Unreviewed. Confirming locks this step against “Refresh draft from sources”.
      </p>
      {needsCheck && (
        <p className="panel-danger">
          The independent verifier found only partial support. Check the evidence before confirming.
        </p>
      )}
      <div className="review-well__actions">
        <Button variant="primary" onClick={onConfirm}>
          {busy ? "Saving…" : "Confirm as drafted"}
        </Button>
        {onEdit && <Button onClick={onEdit}>Edit</Button>}
        <Button variant="danger" onClick={onReject}>
          Reject step
        </Button>
      </div>
    </div>
  );
}

/** Shown when no step is waiting any more (PRD §5.7.5 auto-advance). */
export function AllReviewed() {
  return (
    <div className="review-well review-well--done" role="status">
      <p className="review-well__title">All steps reviewed</p>
      <p className="review-well__note">
        Every step is confirmed, edited, added or rejected. The quality card and Publish arrive in build phase P7.
      </p>
    </div>
  );
}
