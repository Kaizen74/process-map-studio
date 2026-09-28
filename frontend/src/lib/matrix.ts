// The alignment matrix (API_CONTRACT.md → GET /versions/{vid}/alignment-matrix; PRD §5.4 Matrix).
// In lib so components can type their props without src/api. Pure: filters and sorting only; the
// cells come from the backend and are never recomputed here.
import type { StanceOrState } from "./stateGlyph";

export type AlignmentCell = "supports" | "contradicts" | "silent" | "not_applicable";

export interface AlignmentRow {
  element_id: string;
  label: string;
  kind: "activity" | "decision" | "approval" | string;
  sop: AlignmentCell;
  interview: AlignmentCell;
  jd: AlignmentCell;
  artefact: AlignmentCell;
  state: StanceOrState;
  divergence_types: string[];
}

export const COLUMNS: readonly { key: "sop" | "interview" | "jd" | "artefact"; label: string }[] = [
  { key: "sop", label: "SOP / manual" },
  { key: "interview", label: "Interview" },
  { key: "jd", label: "Job description" },
  { key: "artefact", label: "Executed artefacts" },
];

/** B.5 divergence types, in plain words. */
export const DIVERGENCE_TYPES: readonly { value: string; label: string }[] = [
  { value: "sequence", label: "Sequence" },
  { value: "ownership", label: "Ownership" },
  { value: "threshold", label: "Threshold" },
  { value: "trigger", label: "Trigger" },
  { value: "exception", label: "Exception" },
  { value: "omission", label: "Omission" },
];

export function divergenceLabel(type: string): string {
  return DIVERGENCE_TYPES.find((d) => d.value === type)?.label ?? type;
}

/** Most serious first: an executed artefact contradicting the account, then disagreement, then
 * one-sided accounts (a documented-only control may be one nobody performs), then agreement. */
const SEVERITY: readonly string[] = [
  "trace_contradicted",
  "contested",
  "documented_only",
  "practiced_only",
  "not_assessed",
  "corroborated",
];

export type MatrixSort = "process" | "severity";

/** Rows with any of the chosen divergence types (none chosen = every row). */
export function filterRows(rows: readonly AlignmentRow[], types: ReadonlySet<string>): AlignmentRow[] {
  if (types.size === 0) return [...rows];
  return rows.filter((row) => row.divergence_types.some((t) => types.has(t)));
}

/** Process order as served, or most serious first (more divergence types first, then process order). */
export function sortRows(rows: readonly AlignmentRow[], sort: MatrixSort): AlignmentRow[] {
  if (sort === "process") return [...rows];
  const rank = (row: AlignmentRow) => {
    const index = SEVERITY.indexOf(row.state);
    return index === -1 ? SEVERITY.length : index;
  };
  return rows
    .map((row, position) => ({ row, position }))
    .sort(
      (a, b) =>
        rank(a.row) - rank(b.row) ||
        b.row.divergence_types.length - a.row.divergence_types.length ||
        a.position - b.position,
    )
    .map(({ row }) => row);
}

/** How many rows carry each divergence type (for the filter chips). */
export function divergenceCounts(rows: readonly AlignmentRow[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const row of rows) for (const t of row.divergence_types) counts.set(t, (counts.get(t) ?? 0) + 1);
  return counts;
}
