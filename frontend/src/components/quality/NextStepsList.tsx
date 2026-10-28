import type { ReactNode } from "react";
import type { NextStep } from "../../lib/reviewTypes";

export interface NextStepsListProps {
  steps: readonly NextStep[];
  /** Show only the first few (the Review card shows three); the rest are counted. */
  limit?: number;
  /** Open the step an item is about. */
  onSelect: (elementId: string) => void;
  /** The one-click actions of a step (accept, discard, review the next one), if any. */
  actions?: (step: NextStep) => ReactNode;
}

const SHOWN_ITEMS = 5;

/**
 * What is left before publishing, numbered in the order to do it (2026-10-28, Eric: "not sure
 * what I need to do when"). Each step says what to do in plain words; items open their step.
 */
export function NextStepsList({
  steps,
  limit,
  onSelect,
  actions,
}: NextStepsListProps) {
  const shown = limit ? steps.slice(0, limit) : steps;
  const later = steps.length - shown.length;
  return (
    <>
      <ol className="next-steps" aria-label="What to do before publishing">
        {shown.map((step) => (
          <li key={step.key} className="next-steps__step">
            <p className="next-steps__title">{step.title}</p>
            <p className="next-steps__detail">{step.detail}</p>
            {step.items.length > 0 && (
              <ul className="next-steps__items">
                {step.items.slice(0, SHOWN_ITEMS).map((item, index) => (
                  <li key={`${step.key}-${index}`}>
                    {item.element_id ? (
                      <button
                        type="button"
                        className="next-steps__item"
                        onClick={() =>
                          item.element_id && onSelect(item.element_id)
                        }
                      >
                        {item.message}
                      </button>
                    ) : (
                      <span className="next-steps__item">{item.message}</span>
                    )}
                  </li>
                ))}
                {step.items.length > SHOWN_ITEMS && (
                  <li className="next-steps__more">
                    and {step.items.length - SHOWN_ITEMS} more
                  </li>
                )}
              </ul>
            )}
            {actions && (
              <div className="next-steps__actions">{actions(step)}</div>
            )}
          </li>
        ))}
      </ol>
      {later > 0 && (
        <p className="next-steps__later">
          Then {later} more {later === 1 ? "thing" : "things"} before
          publishing.
        </p>
      )}
    </>
  );
}
