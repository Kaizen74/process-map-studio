import { DISPOSITION_LABELS, MODE_LABELS, type StepGapFinding } from "../../lib/gap";
import { PanelSection } from "../panel";
import { SeverityBadge } from "./FindingCard";
import "./gap.css";

export interface GapFindingsSectionProps {
  items: readonly StepGapFinding[];
  onOpen: (analysisId: string) => void;
}

/**
 * Detail panel section 11, Gap findings (PRD §5.7.7): only when the step is linked to findings;
 * one line each (mode, severity, title, decision) opening the report. No map marker is added.
 */
export function GapFindingsSection({ items, onOpen }: GapFindingsSectionProps) {
  if (items.length === 0) return null;
  return (
    <PanelSection title="Gap findings">
      <ul className="step-gap-findings">
        {items.map((f) => (
          <li key={f.id} className="step-gap-findings__row">
            <span className="finding__meta">{MODE_LABELS[f.mode]}</span>
            <SeverityBadge severity={f.severity} />
            <span>{f.title}</span>
            <span className="finding__meta">Decision: {DISPOSITION_LABELS[f.disposition]}</span>
            <button type="button" className="btn btn--link" onClick={() => onOpen(f.analysis_id)}>
              Open the report<span className="visually-hidden"> for “{f.title}”</span>
            </button>
          </li>
        ))}
      </ul>
    </PanelSection>
  );
}
