import type { GraphElement, GraphRole } from "./mapTypes";

// Who decides and who is accountable (PRD §3.20; DECISIONS 110), the same rules as the backend
// (services/accountability.py) and the Capability Compass: the decider in practice is the step's
// decider, or its lane when it names none; accountable is the roles holding A, joined with " / ";
// contested when an A is contested or two roles hold it. "Decides ≠ accountable" when some role
// holds A and the two differ, ignoring case and punctuation.

const DECIDING = new Set(["decision", "approval"]);

export interface Rights {
  onPaper: string;
  decidedBy: string;
  accountable: string;
  contested: boolean;
}

export function same(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s_]/gu, " ")
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

export function rightsOf(e: GraphElement, roles: readonly GraphRole[]): Rights | null {
  if (!DECIDING.has(e.kind)) return null;
  const names = new Map(roles.map((r) => [r.id, r.name]));
  const holders = e.raci.filter((r) => r.letter === "A");
  const accountable = [...new Set(holders.map((r) => names.get(r.role_id) ?? ""))].filter(Boolean);
  const paper = e.paper_decider;
  return {
    onPaper: paper?.status === "named" ? (names.get(paper.role_id ?? "") ?? "") : "",
    decidedBy: names.get(e.decision.decider_role_id ?? e.lane_role_id ?? "") ?? "",
    accountable: accountable.join(" / "),
    contested: holders.length > 0 && (holders.some((r) => r.contested) || accountable.length > 1),
  };
}

export const splits = (r: Rights) => Boolean(r.accountable) && same(r.accountable) !== same(r.decidedBy);
export const paperDiffers = (r: Rights) => Boolean(r.onPaper) && same(r.onPaper) !== same(r.decidedBy);

export interface RaciCounts {
  decisions: number;
  paperDiffers: number;
  split: number;
  contested: number;
}

export function raciCounts(steps: readonly GraphElement[], roles: readonly GraphRole[]): RaciCounts {
  const found = steps.map((e) => rightsOf(e, roles)).filter((r): r is Rights => r !== null);
  return {
    decisions: found.length,
    paperDiffers: found.filter(paperDiffers).length,
    split: found.filter(splits).length,
    contested: found.filter((r) => r.contested).length,
  };
}
