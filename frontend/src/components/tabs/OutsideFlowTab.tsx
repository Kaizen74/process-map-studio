import { plural } from "../../lib/format";
import type { OutsideFlowClaims, PassageClaim } from "../../lib/reviewTypes";

export interface OutsideFlowTabProps {
  data: OutsideFlowClaims;
  onOpenPassage: (claim: PassageClaim) => void;
  /** Add as step from this passage; omitted where the version can't change. */
  onAddStep?: ((claim: PassageClaim) => void) | undefined;
}

/** What the documents say about other flows, in words: "2 claims and 1 question". */
function counted(data: OutsideFlowClaims): string {
  const parts = [
    data.items.length ? plural(data.items.length, "claim") : "",
    data.questions.length ? plural(data.questions.length, "question") : "",
  ];
  return parts.filter(Boolean).join(" and ");
}

/**
 * Outside this flow (DECISIONS 81, 83): claims found in the documents that passed every check but
 * describe another flow, and the reading's open questions about it, so they are kept off this map.
 * Nothing is dropped: Eric can read each passage and, if a claim belongs here after all, add the
 * step himself.
 */
export function OutsideFlowTab({ data, onOpenPassage, onAddStep }: OutsideFlowTabProps) {
  return (
    <div className="tab-stack">
      <p className="tab-intro">
        {data.total === 0
          ? "Every claim in the documents belongs to this flow."
          : `${counted(data)} in your documents are about another flow, so they are kept off this map. To map that flow, use Map another flow from these sources in Setup.`}
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
      {data.questions.length > 0 && (
        <section aria-labelledby="outside-questions">
          <h3 id="outside-questions" className="tab-group__title">
            Questions about another flow
          </h3>
          <ul className="rejected">
            {data.questions.map((q, n) => (
              <li key={`${q.segment_id ?? "none"}-${n}`} className="rejected__item">
                <p className="rejected__claim">{q.question}</p>
                <p className="rejected__meta">
                  {q.source_name}
                  {q.anchor && (
                    <>
                      {" "}
                      · <span className="mono">{q.anchor}</span>
                    </>
                  )}
                </p>
                <div className="rejected__actions">
                  {q.passage_available && q.segment_id ? (
                    <button
                      type="button"
                      className="btn btn--link"
                      onClick={() =>
                        onOpenPassage({ id: `question-${n}`, claim_text: q.question, source_id: q.source_id,
                          source_name: q.source_name, anchor: q.anchor, passage_available: true,
                          segment_id: q.segment_id }) // prettier-ignore
                      }
                    >
                      Open passage
                    </button>
                  ) : (
                    <span className="rejected__missing">Passage missing</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
