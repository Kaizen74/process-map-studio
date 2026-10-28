import { plural } from "../../lib/format";
import type { OutsideFlowClaim, OutsideFlowClaims } from "../../lib/reviewTypes";

export interface OutsideFlowTabProps {
  data: OutsideFlowClaims;
  onOpenPassage: (claim: OutsideFlowClaim) => void;
  /** Add as step from this passage; omitted where the version can't change. */
  onAddStep?: ((claim: OutsideFlowClaim) => void) | undefined;
}

/**
 * Outside this flow (DECISIONS 81): claims found in the documents that passed every check but
 * describe another flow, so they are kept off this map. Nothing is dropped: Eric can read each
 * passage and, if it belongs here after all, add the step himself.
 */
export function OutsideFlowTab({ data, onOpenPassage, onAddStep }: OutsideFlowTabProps) {
  return (
    <div className="tab-stack">
      <p className="tab-intro">
        {data.total === 0
          ? "Every claim in the documents belongs to this flow."
          : `${plural(data.total, "claim")} in your documents describe another flow, so they are kept off this map. To map that flow, use Map another flow from these sources in Setup.`}
      </p>
      {data.items.length > 0 && (
        <ul className="rejected">
          {data.items.map((item) => (
            <li key={item.id} className="rejected__item">
              <p className="rejected__claim">{item.claim_text}</p>
              <p className="rejected__meta">
                {item.source_name}
                {item.anchor && (
                  <>
                    {" "}
                    · <span className="mono">{item.anchor}</span>
                  </>
                )}
              </p>
              <div className="rejected__actions">
                {item.passage_available && item.segment_id ? (
                  <>
                    <button type="button" className="btn btn--link" onClick={() => onOpenPassage(item)}>
                      Open passage
                    </button>
                    {onAddStep && (
                      <button type="button" className="btn btn--link" onClick={() => onAddStep(item)}>
                        Add as step from this passage
                      </button>
                    )}
                  </>
                ) : (
                  <span className="rejected__missing">Passage missing</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
