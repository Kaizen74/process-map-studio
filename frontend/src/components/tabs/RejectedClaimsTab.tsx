import { plural } from "../../lib/format";
import type { RejectedClaim, RejectedClaims } from "../../lib/reviewTypes";

export interface RejectedClaimsTabProps {
  data: RejectedClaims;
  onOpenPassage: (claim: RejectedClaim) => void;
  /** Add as step from this passage; omitted where the version can't change. */
  onAddStep?: ((claim: RejectedClaim) => void) | undefined;
}

/**
 * Rejected claims (PRD §5.7.10, §3.8 G12): claims that failed a check and never reach the map.
 * Eric can read the passage behind one and, if the step is real, add it himself.
 */
export function RejectedClaimsTab({ data, onOpenPassage, onAddStep }: RejectedClaimsTabProps) {
  return (
    <div className="tab-stack">
      <p className="tab-intro">
        {data.total === 0
          ? "No claims were rejected. Every claim Claude made was found in your documents."
          : `${plural(data.total, "claim")} failed a check and will never appear on the map.`}{" "}
        {plural(data.scrub_count, "name")} replaced by roles;{" "}
        {plural(data.instruction_like_count, "instruction-like passage")} treated as data and ignored.
      </p>
      {data.items.length > 0 && (
        <ul className="rejected">
          {data.items.map((item) => (
            <li key={item.id} className="rejected__item">
              <p className="rejected__claim">
                <s>{item.claim_text}</s>
              </p>
              <p className="rejected__reason">{item.reason}</p>
              <p className="rejected__meta">
                <span className="mono">
                  {item.guardrail} · {item.stage}
                </span>{" "}
                · {item.source_name}
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
