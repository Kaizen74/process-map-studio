import { Button } from "../../components/common";

/** The panel with nothing selected (PRD §5.6): how to review, what the marks mean, where to start. */
export function HowToReview({ onStart, readOnly = false }: { onStart: (() => void) | null; readOnly?: boolean }) {
  return (
    <div className="panel-card">
      <h2 className="panel-card__title">How to review</h2>
      <ul className="how-to">
        <li>Click a step on the map, a row of the table, or a segment of the progress bar to see its details and evidence.</li>
        <li>Each piece of evidence opens its source at the exact passage.</li>
        <li>A dashed outline means the step hasn't been reviewed yet. An orange dot marks a key constraint.</li>
        {readOnly ? (
          <li>This version is published and can't change. To change it, reopen it as a new draft.</li>
        ) : (
          <li>Confirm, edit or reject each step; the next step that needs you opens by itself.</li>
        )}
        <li>
          Press <kbd className="mono">?</kbd> for keyboard shortcuts: J and K move between steps
          {readOnly ? ", 1 to 4 switch lens." : ", C confirms, E edits, R rejects."}
        </li>
      </ul>
      {onStart && (
        <Button variant="primary" onClick={onStart}>
          Start with the first step that needs attention
        </Button>
      )}
    </div>
  );
}
