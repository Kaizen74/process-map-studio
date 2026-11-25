// The leadership view (PRD §4 Views, §5.4 Leadership; API_CONTRACT.md → Leadership view): shapes
// and plain words. The server works out every figure; nothing is computed here but bar widths.
import type { RealityFigures } from "./reality";
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
  /** P13b (G17): the figures shared with the Reality views, from the frozen snapshot; null while off. */
  reality: RealityFigures | null;
  /** §3.20 (DECISIONS 110): the process at a glance and the data lens (absent before). */
  summary?: ProcessSummary | null;
}

/** §3.20: counted by the server; null means it can't be counted (never 0 for "not known"). */
export interface ProcessSummary {
  process_owner: string;
  steps: number;
  decisions: number;
  approvals: number;
  handoffs: number;
  roles: number;
  rework_loops: number;
  work_min: number | null;
  wait_min: number | null;
  timed_steps: number;
  systems: number | null;
  handoffs_known: number;
  handoffs_manual: number | null;
  off_system_steps: number | null;
  no_record_steps: number | null;
  steps_differing: number | null;
  links: {
    steps: string[];
    handoffs: string[];
    rework_loops: string[];
    systems: string[];
    handoffs_manual: string[];
    off_system: string[];
    no_record: string[];
  };
}

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** "14 h", "2.5 h". */
export function hours(min: number): string {
  const h = min / 60;
  return `${Number.isInteger(h) ? h : h.toFixed(1)} h`;
}

/** The leadership line, in the brief's words (§3.20). */
export function summaryLine(s: ProcessSummary): string {
  const time =
    s.work_min === null && s.wait_min === null
      ? "times not recorded"
      : `work ${s.work_min === null ? "not recorded" : hours(s.work_min)}, waiting ${
          s.wait_min === null ? "not recorded" : hours(s.wait_min)
        }`;
  return [
    count(s.steps, "step", "steps"),
    count(s.decisions, "decision", "decisions"),
    count(s.approvals, "approval", "approvals"),
    `${count(s.handoffs, "handoff", "handoffs")} between ${count(s.roles, "role", "roles")}`,
    count(s.rework_loops, "rework loop", "rework loops"),
    time,
    `process owner: ${s.process_owner || "not named"}`,
  ].join(" · ");
}

export interface DataFigure {
  key: string;
  text: string;
  ids: string[];
}

/**
 * The data lens line (§3.20): "n systems · n of n handoffs by hand · n steps off-system · n steps
 * with no record". The two Reality counts are left out while those views are off.
 */
export function dataFigures(s: ProcessSummary): DataFigure[] {
  const out: DataFigure[] = [
    {
      key: "systems",
      text: s.systems === null ? "systems not recorded" : count(s.systems, "system", "systems"),
      ids: s.links.systems,
    },
    {
      key: "handoffs_manual",
      text:
        s.handoffs_manual === null
          ? "how data moves not recorded"
          : `${s.handoffs_manual} of ${s.handoffs} handoffs by hand`,
      ids: s.links.handoffs_manual,
    },
  ];
  if (s.off_system_steps !== null)
    out.push({ key: "off_system", text: `${count(s.off_system_steps, "step", "steps")} off-system`, ids: s.links.off_system });
  if (s.no_record_steps !== null)
    out.push({ key: "no_record", text: `${count(s.no_record_steps, "step", "steps")} with no record`, ids: s.links.no_record });
  return out;
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
