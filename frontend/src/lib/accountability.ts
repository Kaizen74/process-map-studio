import type { DataMove, GraphEdge, GraphElement, GraphRole, SystemOfRecord } from "./mapTypes";

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

// The data lens (§3.20): words for the system of record and how data moves at a handoff.

export const DATA_MOVES: readonly DataMove[] = ["system_interface", "re_keyed", "email_spreadsheet", "paper", "verbal"];
const MOVE_WORDS: Readonly<Record<DataMove, string>> = {
  system_interface: "System interface",
  re_keyed: "Re-keyed",
  email_spreadsheet: "Email or spreadsheet",
  paper: "Paper",
  verbal: "Verbal",
};

export function dataMoveWord(move: DataMove | null): string {
  return move ? MOVE_WORDS[move] : "Not known";
}

export function systemWord(record: SystemOfRecord | null, roles: readonly GraphRole[]): string {
  if (record === null) return "Not recorded";
  if (record.status === "none") return "None: paper or memory";
  if (record.status === "other") return `${record.other} (other system)`;
  return roles.find((r) => r.id === record.role_id)?.name ?? "A system no longer on the map";
}

const STEP_KINDS = new Set(["activity", "decision", "approval"]);

/** The handoffs a step starts: lines to a step in another lane (as the backend counts them). */
export function handoffsFrom(
  element: GraphElement,
  elements: readonly GraphElement[],
  edges: readonly GraphEdge[],
  logged: ReadonlySet<string>,
): { edge: GraphEdge; toLabel: string; logged: boolean }[] {
  const steps = new Map(
    elements.filter((e) => STEP_KINDS.has(e.kind) && e.review_status !== "rejected").map((e) => [e.id, e]),
  );
  if (!steps.has(element.id)) return [];
  return edges
    .filter((x) => x.from === element.id && steps.has(x.to) && steps.get(x.to)?.lane_role_id !== element.lane_role_id)
    .map((x) => ({ edge: x, toLabel: steps.get(x.to)?.label ?? "the next step", logged: logged.has(x.to) }));
}
