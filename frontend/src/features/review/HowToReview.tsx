import { Button } from "../../components/common";

/** The panel with nothing selected (PRD §5.6): how to review, what the marks mean, where to start. */
export function HowToReview({ onStart }: { onStart: (() => void) | null }) {
  return (
    <div className="panel-card">
      <h2 className="panel-card__title">How to review</h2>
      <ul className="how-to">
        <li>Click a step on the map, or a segment of the progress bar, to see its details and evidence.</li>
        <li>Each piece of evidence opens its source at the exact passage.</li>
        <li>A dashed outline means the step hasn't been reviewed yet. An orange dot marks a key constraint.</li>
        <li>Lenses change only the line under each step: time, how well sources agree, or confidence.</li>
        <li>Confirming, editing and rejecting steps arrive in build phase P6.</li>
      </ul>
      {onStart && (
        <Button variant="primary" onClick={onStart}>
          Start with the first step that needs attention
        </Button>
      )}
    </div>
  );
}
