import type { PublishBlocker, QualityCard, QualityCheck } from "../../lib/reviewTypes";
import "./quality.css";

const STATUS_WORDS: Readonly<Record<QualityCheck["status"], string>> = {
  pass: "Pass",
  fail: "Fail",
  warning: "Warning",
};

/** Pass = filled circle, fail = open ring, warning = square: shape and word, never colour alone. */
export function CheckGlyph({ status }: { status: QualityCheck["status"] }) {
  return (
    <svg className={`check-glyph check-glyph--${status}`} width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
      {status === "pass" && <circle cx="6" cy="6" r="4.5" />}
      {status === "fail" && <circle cx="6" cy="6" r="4.25" fill="none" strokeWidth="1.5" />}
      {status === "warning" && <rect x="1.75" y="1.75" width="8.5" height="8.5" />}
    </svg>
  );
}

/** The ten checks of the quality card with their details, warnings and legend (PRD §5.7.9). */
export function QualityCardView({ card }: { card: QualityCard }) {
  return (
    <div className="quality">
      <ul className="quality__checks" aria-label="Quality checks">
        {card.checks.map((check) => (
          <li key={check.id} className="quality__check">
            <span className="mono quality__id">{check.id}</span>
            <CheckGlyph status={check.status} />
            <span className="quality__body">
              <span className="quality__name">
                {check.name} <span className="visually-hidden">: {STATUS_WORDS[check.status]}</span>
              </span>
              <span className={check.status === "fail" ? "quality__detail quality__detail--fail" : "quality__detail"}>
                {check.detail}
              </span>
            </span>
          </li>
        ))}
      </ul>
      {card.warnings.length > 0 && (
        <div className="quality__warnings">
          <p className="quality__heading">Also worth a look</p>
          <ul>
            {card.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
      <p className="quality__legend">
        <CheckGlyph status="pass" /> pass · <CheckGlyph status="fail" /> must fix · <CheckGlyph status="warning" /> warning
        only
      </p>
    </div>
  );
}

export interface BlockerListProps {
  blockers: readonly PublishBlocker[];
  /** Go to the step a blocker is about. */
  onSelect: (elementId: string) => void;
}

/** What stops publishing (PRD §5.7.9): each row names its type and, if it has one, opens its step. */
export function BlockerList({ blockers, onSelect }: BlockerListProps) {
  return (
    <ul className="blockers" aria-label="What to fix before publishing">
      {blockers.map((blocker, index) => (
        <li key={`${blocker.type}-${blocker.id}-${index}`}>
          {blocker.element_id ? (
            <button type="button" className="blockers__row" onClick={() => blocker.element_id && onSelect(blocker.element_id)}>
              <span className="mono blockers__type">{blocker.type}</span>
              <span>{blocker.message}</span>
            </button>
          ) : (
            <span className="blockers__row">
              <span className="mono blockers__type">{blocker.type}</span>
              <span>{blocker.message}</span>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
