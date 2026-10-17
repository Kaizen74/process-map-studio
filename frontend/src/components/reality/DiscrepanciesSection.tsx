import { Link } from "react-router";
import type { CodeView, SnapshotIntent } from "../../lib/reality";
import { RESULT_LABELS, verdictText } from "../../lib/reality";
import { PanelSection } from "../panel";
import { ImpactWord } from "./RealityBits";
import "./reality.css";

export interface DiscrepanciesSectionProps {
  codes: readonly CodeView[];
  intents: readonly SnapshotIntent[];
  /** The Reality screen's address with a code selected. */
  linkFor: (code: string) => string;
}

/**
 * Detail panel section 12, Discrepancies (PRD §5.7.7; P13b): one line per X code at this step,
 * read from the version's Reality snapshot, with a link to the Reality screen with that code
 * selected. No map marker is added (constraint 17).
 */
export function DiscrepanciesSection({ codes, intents, linkFor }: DiscrepanciesSectionProps) {
  if (codes.length === 0 && intents.length === 0) return null;
  return (
    <PanelSection title="Discrepancies">
      <ul className="discrepancy-list">
        {codes.map((c) => (
          <li key={c.code} className="discrepancy-row">
            <span className="discrepancy-row__meta">
              <span className={`x-tag x-tag--${c.impact_class}`}>{c.code}</span>
              <span>{c.types.join(" ")}</span>
              <span>
                {c.delta.text} ({c.delta.label})
              </span>
              <ImpactWord code={c} />
            </span>
            {c.verdict?.shown && <span className="discrepancy-row__verdict">Verdict: {verdictText(c.verdict)}</span>}
            <Link to={linkFor(c.code)}>
              Open on the Reality screen{" "}
            <span className="visually-hidden">({c.code})</span>
            </Link>
          </li>
        ))}
        {intents.map((i) => (
          <li key={i.id} className="discrepancy-row">
            <span className="discrepancy-row__meta">Intent: {i.text}</span>
            <span className="discrepancy-row__verdict">{RESULT_LABELS[i.result] ?? i.result}</span>
          </li>
        ))}
      </ul>
    </PanelSection>
  );
}
