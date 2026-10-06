// The table view of the map (PRD §5.7.4): one row per step with every value the map shows, so
// it is the accessible equivalent of the map. Pure; components/table draws what this returns.

import { durationText } from "./lens";
import type { Graph, GraphElement } from "./mapTypes";

export type TableFilter = "all" | "needs_check" | "unreviewed" | "contested";

export interface StepRow {
  id: string;
  label: string;
  kind: string;
  lane: string;
  provenance: string;
  sourceState: string;
  time: string;
  confidence: string;
  review: string;
  needsCheck: boolean;
  rejected: boolean;
  /** "Part of: <landscape activity>" for a practice step under one (K2), else "". */
  partOf: string;
}

const STEPS = new Set(["activity", "decision", "approval"]);
const KINDS: Readonly<Record<string, string>> = { activity: "Activity", decision: "Decision", approval: "Approval" };
const PROVENANCE: Readonly<Record<string, string>> = { O: "O · observed", I: "I · inferred", R: "R · recommended" };
const REVIEW: Readonly<Record<string, string>> = {
  draft: "Unreviewed",
  confirmed: "Confirmed",
  edited: "Edited",
  added: "Added",
  rejected: "Rejected",
};

const MATCHES: Readonly<Record<TableFilter, (e: GraphElement) => boolean>> = {
  all: () => true,
  needs_check: (e) => e.needs_check && e.review_status === "draft",
  unreviewed: (e) => e.review_status === "draft",
  contested: (e) => e.source_state === "contested",
};

export const TABLE_FILTERS: readonly { value: TableFilter; label: string }[] = [
  { value: "all", label: "All steps" },
  { value: "needs_check", label: "Needs check" },
  { value: "unreviewed", label: "Unreviewed" },
  { value: "contested", label: "Contested" },
];

/** The filters with how many steps each shows: "Needs check (1)". */
export function filterOptions(graph: Graph): { value: TableFilter; label: string }[] {
  const steps = graph.elements.filter((e) => STEPS.has(e.kind));
  return TABLE_FILTERS.map((f) => ({ value: f.value, label: `${f.label} (${steps.filter(MATCHES[f.value]).length})` }));
}

/** The steps in process order, as table rows, with only those the filter shows. */
export function tableRows(graph: Graph, filter: TableFilter): StepRow[] {
  const roles = new Map(graph.roles.map((r) => [r.id, r.name]));
  const labels = new Map(graph.elements.map((e) => [e.id, e.label]));
  // Practice steps are listed right after the landscape activity they are part of (§3.9 rule 10).
  const shown = graph.elements.filter((e) => STEPS.has(e.kind) && MATCHES[filter](e));
  const parentShown = (e: (typeof shown)[number]) =>
    e.parent_element_id ? shown.some((p) => p.id === e.parent_element_id) : false;
  const grouped = shown.flatMap((e) =>
    parentShown(e) ? [] : [e, ...shown.filter((c) => c.parent_element_id === e.id)],
  );
  return grouped
    .map((e) => ({
      id: e.id,
      label: e.label,
      kind: KINDS[e.kind] ?? e.kind,
      lane: roles.get(e.lane_role_id ?? "") ?? "",
      provenance: PROVENANCE[e.provenance] ?? e.provenance,
      sourceState: e.source_state,
      time: durationText(e.time.work_min, e.time.wait_min) || (e.kind === "decision" ? "" : "No time stated"),
      confidence: e.confidence === null ? "" : e.confidence.toFixed(2),
      review: e.needs_check && e.review_status === "draft" ? "Unreviewed · needs check" : (REVIEW[e.review_status] ?? e.review_status),
      needsCheck: e.needs_check && e.review_status === "draft",
      rejected: e.review_status === "rejected",
      partOf: e.parent_element_id ? `Part of: ${labels.get(e.parent_element_id) ?? ""}` : "",
    }));
}
