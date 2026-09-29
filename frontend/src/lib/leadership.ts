// The leadership view (PRD §4 Views, §5.4 Leadership; API_CONTRACT.md → Leadership view): shapes
// and plain words. The server works out every figure; nothing is computed here but bar widths.
import type { AiFlagItem } from "./registers";

export interface PhaseLinks {
  work: string[];
  wait: string[];
  rework_loops: string[];
  handoffs: string[];
  divergence: Record<string, string[]>;
}

export interface PhaseFacts {
  phase_id: string | null;
  name: string;
  work_min: number;
  wait_min: number;
  rework_loops: number;
  handoffs: number;
  divergence_counts: Record<string, number>;
  links: PhaseLinks;
}

export interface CauseSummary {
  cause_type: string;
  systemic: boolean;
  reason: string;
  phases: { phase_id: string | null; name: string }[];
  lanes: string[];
  evidence_weight: { supporting: number; sources: number };
  confidence: number | null;
  constraints: { element_id: string; label: string; text: string; is_key: boolean }[];
  element_ids: string[];
}

export interface DecisionNeeded {
  cause_type: string;
  text: string;
}

export interface LeadershipView {
  version: { id: string; label: string; state: string };
  facts: { phases: PhaseFacts[]; sources: number };
  interpretation: { causes: CauseSummary[] };
  recommendation: {
    recoverable_wait_min: number;
    recoverable_wait_element_ids: string[];
    rework_loops: number;
    rework_element_ids: string[];
    ai_flags: AiFlagItem[];
    decisions_needed: DecisionNeeded[];
  };
}

/** "20 min", "1.5 min", "0 min". */
export function minutes(value: number): string {
  return `${Number.isInteger(value) ? value : value.toFixed(1)} min`;
}

/** "Supported by 3 of 5 sources". */
export function weightText(w: CauseSummary["evidence_weight"]): string {
  return `Supported by ${w.supporting} of ${w.sources} ${w.sources === 1 ? "source" : "sources"}`;
}

/** "Confidence 73%", or that none of its steps has one. */
export function confidenceText(confidence: number | null): string {
  return confidence === null ? "Confidence not worked out" : `Confidence ${Math.round(confidence * 100)}%`;
}

/** Bar widths as percentages of the longest phase (work + wait), so phases compare at a glance. */
export function barWidths(phases: readonly PhaseFacts[]): { work: number; wait: number }[] {
  const longest = Math.max(0, ...phases.map((p) => p.work_min + p.wait_min));
  return phases.map((p) =>
    longest === 0 ? { work: 0, wait: 0 } : { work: (p.work_min / longest) * 100, wait: (p.wait_min / longest) * 100 },
  );
}
