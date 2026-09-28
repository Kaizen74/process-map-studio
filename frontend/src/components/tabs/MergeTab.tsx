import { Button, Chip } from "../common";
import type { MergeProposal } from "../../lib/reviewTypes";

export type MergeChoice = "accepted" | "rejected" | "split";

export interface MergeTabProps {
  proposals: readonly MergeProposal[];
  busyId: string | null;
  /** Accept merge / Keep separate / Split; omitted where the version can't change. */
  onDecide?: ((proposalId: string, decision: MergeChoice) => void) | undefined;
  onGoTo: (elementId: string) => void;
}

const STATES: Readonly<Record<string, string>> = {
  pending: "Waiting for you",
  accepted: "Merged",
  rejected: "Kept separate",
  split: "Split again",
};

/**
 * Merge decisions (PRD §5.7.10): steps Claude thought might be one step described differently,
 * their claims side by side with quotes and similarity. Accept merge · Keep separate · Split.
 */
export function MergeTab({ proposals, busyId, onDecide, onGoTo }: MergeTabProps) {
  if (proposals.length === 0) {
    return <p className="tab-empty">No merge decisions. Claude found no steps that looked like the same step.</p>;
  }
  return (
    <ul className="tab-cards">
      {proposals.map((p) => {
        const busy = busyId === p.id;
        return (
          <li key={p.id} className="merge">
            <div className="merge__header">
              <p className="merge__title">{p.proposed_label}</p>
              <span className="merge__similarity">
                similarity <span className="mono">{p.similarity.toFixed(2)}</span>
              </span>
              <Chip tone={p.decision === "pending" ? "danger" : "neutral"} dashed={p.decision === "pending"}>
                {STATES[p.decision] ?? p.decision}
              </Chip>
              {p.element_id && (
                <button type="button" className="btn btn--link" onClick={() => p.element_id && onGoTo(p.element_id)}>
                  Go to the merged step
                </button>
              )}
            </div>
            <div className="merge__groups">
              {p.groups.map((g, i) => (
                <section key={`${g.label}-${i}`} className="merge__group" aria-label={g.label}>
                  <p className="merge__group-title">{g.label}</p>
                  <p className="merge__group-meta">
                    {g.kind} · {g.lane_role_name}
                  </p>
                  <ul className="merge__claims">
                    {g.claims.map((c, j) => (
                      <li key={j}>
                        <p>{c.text}</p>
                        <p className="merge__quote">“{c.quote}”</p>
                        <p className="merge__source">
                          {c.source_name} · <span className="mono">{c.anchor}</span>
                        </p>
                      </li>
                    ))}
                  </ul>
                  {g.element_id && (
                    <button type="button" className="btn btn--link" onClick={() => g.element_id && onGoTo(g.element_id)}>
                      Go to {g.label}
                    </button>
                  )}
                </section>
              ))}
            </div>
            {onDecide && (
              <div className="merge__actions">
                {(p.decision === "pending" || p.decision === "rejected") && (
                  <Button variant="primary" onClick={() => onDecide(p.id, "accepted")}>
                    {busy ? "Saving…" : "Accept merge"}
                  </Button>
                )}
                {p.decision === "pending" && (
                  <Button onClick={() => onDecide(p.id, "rejected")}>Keep separate</Button>
                )}
                {p.decision === "accepted" && <Button onClick={() => onDecide(p.id, "split")}>{busy ? "Saving…" : "Split"}</Button>}
                {p.decision === "split" && (
                  <p className="tab-intro">Split back into the steps as drafted. Change them with Edit, Reject or Add step.</p>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
