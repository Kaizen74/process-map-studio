import type { GraphElement } from "../../lib/mapTypes";
import { Chip } from "../common";
import "./panel.css";

const KINDS: Readonly<Record<string, string>> = {
  activity: "Activity",
  decision: "Decision",
  approval: "Approval",
  start: "Start",
  end: "End",
};
const PROVENANCE: Readonly<Record<string, string>> = { O: "Observed · O", I: "Inferred · I", R: "Recommended · R" };
const STATES: Readonly<Record<string, string>> = {
  corroborated: "Corroborated",
  documented_only: "Documented only",
  practiced_only: "Practiced only",
  contested: "Contested",
  trace_contradicted: "Trace contradicted",
  not_assessed: "Not assessed",
};
const REVIEW: Readonly<Record<string, string>> = {
  draft: "Unreviewed",
  confirmed: "Confirmed",
  edited: "Edited",
  added: "Added",
  rejected: "Rejected",
};
const STEPS = new Set(["activity", "decision", "approval"]);

export interface PanelHeaderProps {
  element: GraphElement;
  laneName: string;
  phaseName: string;
  /** The landscape activity a practice step is part of (K2), or "". */
  partOf?: string | undefined;
}

/** Overline "Kind · Phase", the title, "Lane · role" and the chips in PRD §5.7.5 order. */
export function PanelHeader({ element, laneName, phaseName, partOf }: PanelHeaderProps) {
  const kind = KINDS[element.kind] ?? element.kind;
  const step = STEPS.has(element.kind);
  const contested = element.source_state === "contested" || element.source_state === "trace_contradicted";
  return (
    <header className="panel-header">
      <p className="panel-header__overline">{[element.code, kind, phaseName].filter(Boolean).join(" · ")}</p>
      <h2 className="panel-header__title" id="panel-title">
        {element.label}
      </h2>
      {laneName && <p className="panel-header__lane">Lane · {laneName}</p>}
      {partOf && <p className="panel-header__lane">Part of: {partOf}</p>}
      {step && (
        <div className="panel-header__chips">
          <Chip>{kind}</Chip>
          <Chip>{PROVENANCE[element.provenance] ?? element.provenance}</Chip>
          <Chip tone={contested ? "danger" : "neutral"}>{STATES[element.source_state] ?? element.source_state}</Chip>
          {element.divergence_types.map((d) => (
            <Chip key={d} tone="danger">
              Divergence · {d.replaceAll("_", " ")}
            </Chip>
          ))}
          {element.confidence !== null && (
            <Chip tone={element.confidence < 0.6 ? "danger" : "neutral"}>
              Confidence <span className="mono">{element.confidence.toFixed(2)}</span>
            </Chip>
          )}
          {element.needs_check && <Chip tone="danger">Needs check</Chip>}
          <Chip dashed={element.review_status === "draft"} tone={element.review_status === "draft" ? "neutral" : "good"}>
            {REVIEW[element.review_status] ?? element.review_status}
          </Chip>
        </div>
      )}
    </header>
  );
}
