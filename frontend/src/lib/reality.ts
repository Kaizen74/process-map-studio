// The Reality snapshot as the backend sends it (API_CONTRACT.md → Reality snapshot; PRD §3.18,
// §5.12; P13b, P13c). Formatting only: every number, word, headline and position comes from the
// backend; nothing here computes a figure or a layout (constraints 20 and 26).

import type { CSSProperties } from "react";

export type ImpactClass = "control_exposure" | "time_impact" | "capacity_drain" | "workaround";
export type ImpactGlyph = "triangle" | "clock" | "bars" | "dotted_square";
export type ViewId = "rv1" | "rv2" | "rv3" | "rv4" | "rv5" | "rv6" | "rv7";

export interface Figure {
  id: string;
  value: number | null;
  unit: string;
  text: string;
  label: string;
  percent_type: string | null;
}

export interface Tile {
  figure: Figure;
  caption: string;
}

export interface EvidenceSummary {
  documents: number;
  interviews: number;
  cases: number | null;
  text: string;
}

export interface Column {
  id: string;
  name: string;
  kind: string;
  step_keys: string[];
}

export interface Chips {
  documents: boolean;
  interviews: boolean;
  system: boolean;
}

export interface CodeEvidence {
  documents: number;
  interviews: number;
  system_cases: number | null;
  chips: Chips;
  sentence: string;
}

export interface CodeVerdict {
  suggested: string | null;
  decided: string | null;
  shown: string | null;
  status: "suggested" | "confirmed";
  reason: string;
  note: string;
}

export interface CodeLocation {
  kind: string;
  keys: string[];
}

export interface CodeView {
  code: string;
  item_id: string;
  title: string;
  types: string[];
  impact_class: ImpactClass;
  impact_word: string;
  glyph: ImpactGlyph;
  impact_note: string;
  location: CodeLocation;
  element_ids: string[];
  column_id: string | null;
  delta: Figure;
  minutes: Figure | null;
  hours: Figure | null;
  verdict: CodeVerdict | null;
  evidence: CodeEvidence;
  control: boolean;
  shown: boolean;
  rank: number;
}

export interface SnapshotIntent {
  id: string;
  kind: string;
  text: string;
  scope: string;
  step_keys: string[];
  result: "met" | "not_met" | "unknown";
  target: string;
}

export interface Callout {
  code: string | null;
  impact_class: ImpactClass | null;
  lines: string[];
}

export interface Availability {
  state: "ready" | "partial" | "missing";
  message: string;
  action: "add_intent" | "upload_documents" | "import_log" | "draft" | null;
}

export interface ViewTable {
  columns: string[];
  rows: string[][];
}

export interface Route {
  id: string;
  name: string;
  documented: boolean;
  share: Figure;
  codes: string[];
  impact_class: ImpactClass | null;
  other_count: number;
}

export interface GlanceModel {
  basis: "cases" | "steps";
  routes: Route[];
}

export interface Trunk {
  x1: number;
  x2: number;
  y: number;
  width: number;
}

export interface Ribbon {
  route_id: string;
  path: string;
  width: number;
  style: string;
  label_x: number;
  label_y: number;
}

export interface GlanceGeometry {
  width: number;
  height: number;
  trunk: Trunk;
  ribbons: Ribbon[];
  scale_note: string;
}

export interface StackItem {
  kind: string;
  key: string | null;
  label: string;
  figure: Figure | null;
  code: string | null;
  impact_class: ImpactClass | null;
  result: "met" | "not_met" | "unknown" | null;
  note: string;
}

export interface StackCell {
  column_id: string;
  items: StackItem[];
}

export interface Band {
  id: string;
  name: string;
  evidence: string;
  state: "ready" | "partial" | "missing";
  message: string;
  cells: StackCell[];
}

export interface Lens {
  column_id: string;
  label: string;
}

export interface StackModel {
  bands: Band[];
  lens: Lens | null;
  highlighted: string[];
  listed: string[];
}

export interface Box {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Mark {
  kind: string;
  band_id: string;
  column_id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  lines: string[];
  code: string | null;
  key: string | null;
  impact_class: ImpactClass | null;
  style: string;
}

export interface Label {
  id: string;
  x: number;
  y: number;
  lines: string[];
}

export interface LensBox {
  x: number;
  y: number;
  width: number;
  height: number;
  label_x: number;
  label_y: number;
}

export interface StackGeometry {
  width: number;
  height: number;
  columns: Box[];
  bands: Box[];
  marks: Mark[];
  lens: LensBox | null;
  column_labels: Label[];
  band_labels: Label[];
}

export interface Quadrant {
  id: string;
  name: string;
  meaning: string;
}

export interface Placed {
  code: string;
  zone: string;
}

export interface FixModel {
  quadrants: Quadrant[];
  circles: Placed[];
  ask: string[];
  decide_first: string[];
  limit: number;
  note: string;
}

export interface Zone {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  label_x: number;
  label_y: number;
}

export interface Circle {
  code: string;
  cx: number;
  cy: number;
  r: number;
}

export interface FixGeometry {
  width: number;
  height: number;
  zones: Zone[];
  circles: Circle[];
  labels: Label[];
  scale_note: string;
}

export interface ViewBase {
  id: ViewId;
  title: string;
  headline: string;
  callouts: Callout[];
  availability: Availability;
  table: ViewTable;
}

export interface GlanceView extends ViewBase {
  glance: GlanceModel;
  geometry: GlanceGeometry;
}

export interface StackView extends ViewBase {
  stack: StackModel;
  geometry: StackGeometry;
}

export interface FixView extends ViewBase {
  fix: FixModel;
  geometry: FixGeometry;
}

// --- P13c: Redline, Where the time goes, Belief vs evidence, Typical case -------------------

/** One shape placed by the backend; text boxes are top-left x, y with line i at y + 12 + 16 i. */
export interface Shape {
  kind: "rect" | "path" | "line" | "circle" | "text";
  role: string;
  x: number;
  y: number;
  width: number;
  height: number;
  x2: number;
  y2: number;
  r: number;
  path: string;
  lines: string[];
  code: string | null;
  key: string | null;
  impact_class: ImpactClass | null;
  style: "solid" | "dashed" | "dotted" | "double";
}

export interface ShapeGeometry {
  width: number;
  height: number;
  shapes: Shape[];
  scale_note: string;
}

export interface RedlineStep {
  key: string;
  label: string;
  minutes: Figure | null;
  ghost: boolean;
  codes: string[];
}

export interface Markup {
  code: string;
  type: string;
  kind: string;
  keys: string[];
  label: string;
  share: Figure;
  impact_class: ImpactClass;
  drawn: boolean;
  tool: string;
}

export interface RedlinePage {
  id: string;
  name: string;
  step_keys: string[];
}

export interface RedlineModel {
  pages: RedlinePage[];
  steps: RedlineStep[];
  markups: Markup[];
  pills: Figure[];
  listed: string[];
}

export interface TimeColumn {
  column_id: string;
  name: string;
  manual: Figure | null;
  work: Figure | null;
  wait: Figure | null;
  designed: Figure | null;
  extra: Figure | null;
  complete: boolean;
}

export interface TimeCause {
  code: string;
  title: string;
  minutes: Figure;
}

export interface TimeModel {
  columns: TimeColumn[];
  manual_total: Figure | null;
  practice_total: Figure | null;
  multiplier: Figure | null;
  complete: boolean;
  causes: TimeCause[];
}

export interface BeliefRow {
  key: string;
  label: string;
  believed: Figure;
  measured: Figure;
  gap: Figure;
  direction: "longer" | "shorter";
  prevalence: string;
  code: string | null;
  impact_class: ImpactClass | null;
}

export interface BeliefModel {
  rows: BeliefRow[];
  note: string;
  method: string;
}

export interface CaseLane {
  id: string;
  name: string;
  kind: "system" | "tool" | "off_system" | "outside";
}

export interface CaseEvent {
  key: string | null;
  label: string;
  lane_id: string;
  minutes: Figure | null;
  recorded: boolean;
}

export interface CaseModel {
  route_name: string;
  cases: number;
  label: string;
  lanes: CaseLane[];
  events: CaseEvent[];
  designed_finish: Figure | null;
  promise: Figure | null;
  actual_finish: Figure | null;
  tiles: Tile[];
}

export interface RedlineView extends ViewBase {
  redline: RedlineModel;
  geometry: ShapeGeometry;
}

export interface TimeView extends ViewBase {
  time: TimeModel;
  geometry: ShapeGeometry;
}

export interface BeliefView extends ViewBase {
  belief: BeliefModel;
  geometry: ShapeGeometry;
}

export interface CaseView extends ViewBase {
  case: CaseModel;
  geometry: ShapeGeometry;
}

export interface RealityViews {
  rv1: GlanceView;
  rv2: StackView;
  rv3: FixView;
  rv4: RedlineView;
  rv5: TimeView;
  rv6: BeliefView;
  rv7: CaseView;
}

export interface LegendImpact {
  impact_class: ImpactClass;
  word: string;
  glyph: ImpactGlyph;
}

export interface LegendLine {
  style: string;
  meaning: string;
}

export interface Legend {
  impacts: LegendImpact[];
  lines: LegendLine[];
  scales: string[];
  data_label: string;
  /** The key to the D I S evidence boxes; missing in snapshots frozen before copy version 4. */
  evidence_key?: string;
}

export interface RealitySnapshot {
  version_id: string;
  rules_version: string;
  copy_version: string;
  layout_version: string;
  app_version: string;
  inputs_hash: string;
  frozen: boolean;
  draft: boolean;
  process_name: string;
  data_label: string;
  evidence: EvidenceSummary;
  figures: Record<string, Figure>;
  tiles: Tile[];
  columns: Column[];
  columns_note: string;
  codes: CodeView[];
  intents: SnapshotIntent[];
  views: RealityViews;
  legend: Legend;
}

/** What Leadership shares with the Reality views (G17). */
export interface RealityFigures {
  data_label: string;
  tiles: Tile[];
}

// --- Intent statements (API_CONTRACT.md → Intent) ------------------------------------------

export type IntentKind = "promise" | "target" | "control_objective" | "policy_rule";

export interface IntentStatement {
  id: string;
  engagement_id: string;
  scope: string;
  element_stable_key: string | null;
  element_label: string;
  phase_name: string | null;
  kind: IntentKind | string;
  origin: string;
  text: string;
  metric: string | null;
  comparator: string | null;
  target_value: number | null;
  unit: string | null;
  source_id: string | null;
  source_name: string;
  anchor: string;
  quote: string;
  owner_role_id: string | null;
  owner_role_name: string;
  stated_on: string | null;
  label: string;
  verification_status: string;
  rejection_guardrail: string | null;
  status: string;
  note: string;
  created_at: string;
}

export interface IntentFields {
  scope?: string;
  element_stable_key?: string | null;
  phase_name?: string | null;
  kind?: string;
  text?: string;
  metric?: string | null;
  comparator?: string | null;
  target_value?: number | null;
  unit?: string | null;
  owner_role_id?: string;
  stated_on?: string;
}

export interface VerdictDecided {
  item_id: string;
  code: string;
  verdict_decided: string | null;
  verdict_note: string;
  decision_owner_role_id: string | null;
}

// --- words (no figures) --------------------------------------------------------------------

export const VIEW_LABELS: Readonly<Record<ViewId, string>> = {
  rv1: "Glance",
  rv2: "Reality stack",
  rv3: "Fix or keep",
  rv4: "Redline",
  rv5: "Where the time goes",
  rv6: "Belief vs evidence",
  rv7: "Typical case",
};

/** The views in reading order (§5.4 view switcher). */
export const VIEW_ORDER: readonly ViewId[] = ["rv1", "rv2", "rv3", "rv4", "rv5", "rv6", "rv7"];

export const VERDICT_LABELS: Readonly<Record<string, string>> = {
  codify: "Codify",
  correct: "Correct",
  rewrite: "Rewrite",
  ask: "Ask",
  as_designed: "As designed",
};

export const KIND_LABELS: Readonly<Record<string, string>> = {
  promise: "Promise",
  target: "Target",
  control_objective: "Control objective",
  policy_rule: "Policy rule",
};

export const RESULT_LABELS: Readonly<Record<string, string>> = {
  met: "Met",
  not_met: "Not met",
  unknown: "Not known yet",
};

/** The codes at a step, in code order (panel section 12). */
export function codesAt(snapshot: RealitySnapshot, elementId: string): CodeView[] {
  return snapshot.codes.filter((c) => c.element_ids.includes(elementId));
}

/** The confirmed statements covering a step (panel section 12). */
export function intentsAt(snapshot: RealitySnapshot, stableKey: string): SnapshotIntent[] {
  return snapshot.intents.filter((i) => i.step_keys.includes(stableKey));
}

/** "Verdict: Correct (suggested)". */
export function verdictText(verdict: CodeVerdict | null): string {
  if (!verdict?.shown) return "";
  return `${VERDICT_LABELS[verdict.shown] ?? verdict.shown} (${verdict.status})`;
}

/** A drawing's own width (from the backend layout), for "Show full size": the CSS reads it. */
export function canvasWidth(width: number): CSSProperties {
  return { "--canvas-width": `${width}px` } as CSSProperties;
}
