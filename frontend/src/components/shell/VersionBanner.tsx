import type { ReactNode } from "react";
import type { SignalStrength } from "../../lib/reviewTypes";
import { Chip, SignalMeter } from "../common";
import "./shell.css";

export interface ProgressStep {
  id: string;
  label: string;
  review_status: string;
}

export interface VersionBannerProps {
  label: string;
  sources: number;
  /** Activities, decisions and approvals in process order. */
  steps: readonly ProgressStep[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Quality card and Publish (phase P7), on the right. */
  actions?: ReactNode;
  /** How well the sources support the map (P12); shown after the version chip when known. */
  signal?: SignalStrength | null | undefined;
  /** The Capability Compass key and pilot, for a map that started from a hand-off. */
  handoff?: { key: string; pilot: string } | undefined;
}

const REVIEWED = new Set(["confirmed", "edited", "added"]);

function segmentState(status: string): "reviewed" | "rejected" | "open" {
  if (REVIEWED.has(status)) return "reviewed";
  return status === "rejected" ? "rejected" : "open";
}

const SEGMENT_WORDS = { reviewed: "reviewed", rejected: "rejected", open: "not reviewed yet" } as const;

/**
 * The draft's banner (PRD §5.7.1): version chip, what it means, and one progress segment per step
 * in process order. Clicking a segment selects that step. Quality card and Publish come in `actions`.
 */
export function VersionBanner({
  label,
  sources,
  steps,
  selectedId,
  onSelect,
  actions,
  signal,
  handoff,
}: VersionBannerProps) {
  const reviewed = steps.filter((s) => REVIEWED.has(s.review_status)).length;
  return (
    <div className="version-banner">
      <Chip dashed mono>
        Draft {label}
      </Chip>
      {handoff && (
        <Chip mono title="The Capability Compass engagement key and pilot this map belongs to">
          {handoff.key} · {handoff.pilot}
        </Chip>
      )}
      {signal && <SignalMeter signal={signal} compact />}
      <p className="version-banner__text">
        Generated from {sources} {sources === 1 ? "source" : "sources"}. Nothing is published until every step is
        reviewed and the quality card is green.
      </p>
      <div className="version-banner__progress">
        <span className="version-banner__count">
          <span className="mono">{reviewed}</span> of <span className="mono">{steps.length}</span> steps reviewed
        </span>
        <ol className="review-progress" aria-label="Review progress, one step per segment">
          {steps.map((step) => {
            const state = segmentState(step.review_status);
            const selected = step.id === selectedId;
            return (
              <li key={step.id}>
                <button
                  type="button"
                  className={`review-progress__segment review-progress__segment--${state}${selected ? " review-progress__segment--selected" : ""}`}
                  aria-label={`${step.label}, ${SEGMENT_WORDS[state]}`}
                  aria-pressed={selected}
                  title={step.label}
                  onClick={() => onSelect(step.id)}
                />
              </li>
            );
          })}
        </ol>
      </div>
      {actions && <div className="version-banner__actions">{actions}</div>}
    </div>
  );
}
