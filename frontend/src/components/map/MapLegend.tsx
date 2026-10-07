import { WORK_TYPE_LABELS, type Lens } from "../../lib/lens";
import type { WorkType } from "../../lib/mapTypes";
import type { StanceOrState } from "../../lib/stateGlyph";
import type { AsView } from "../../lib/views";
import { StateGlyph, WorkTypeGlyph } from "../common";

const STATES: StanceOrState[] = ["corroborated", "documented_only", "practiced_only", "contested", "trace_contradicted"];

const WORK_TYPES = Object.keys(WORK_TYPE_LABELS) as WorkType[];

export interface MapLegendProps {
  lens: Lens;
  /** The view drawn: "not described" connectors only exist As done (§3.12.11). */
  view?: AsView;
  /** Show the other view is on: ghosted steps are drawn. */
  showOther?: boolean;
}

/** Always under the map (PRD §5.5): shapes, markers and lines, plus the active lens's key. */
export function MapLegend({ lens, view = "done", showOther = false }: MapLegendProps) {
  return (
    <div className="map-legend">
      <ul className="map-legend__list" aria-label="Map legend">
        <li>
          <span className="legend-sample legend-sample--activity" aria-hidden="true" />
          Activity
        </li>
        <li>
          <span className="legend-sample legend-sample--decision" aria-hidden="true" />
          Decision
        </li>
        <li>
          <span className="legend-sample legend-sample--approval" aria-hidden="true" />
          Approval
        </li>
        <li>
          <span className="legend-sample legend-sample--start" aria-hidden="true" />
          Start / end
        </li>
        <li>
          <span className="legend-sample legend-sample--constraint" aria-hidden="true" />
          Key constraint
        </li>
        <li>
          <span className="legend-sample legend-sample--images" aria-hidden="true" />
          Has images
        </li>
        <li>
          <span className="legend-sample legend-sample--unreviewed" aria-hidden="true" />
          Unreviewed
        </li>
        <li>
          <span className="legend-sample legend-sample--back" aria-hidden="true" />
          Rework path
        </li>
        {view === "done" && (
          <li>
            <span className="legend-sample legend-sample--gap" aria-hidden="true" />
            Not described (the lived account doesn't say what happens between)
          </li>
        )}
        {showOther && (
          <li>
            <span className="legend-sample legend-sample--ghost" aria-hidden="true" />
            {view === "done" ? "Only in the documented version" : "Only in practice"}
          </li>
        )}
      </ul>
      {lens !== "plain" && (
        <ul className="map-legend__list map-legend__lens" aria-label="Lens key">
          {lens === "source_state" &&
            STATES.map((state) => (
              <li key={state}>
                <StateGlyph state={state} />
              </li>
            ))}
          {lens === "confidence" && (
            <li>
              <span className="map-bar" aria-hidden="true">
                <span className="map-bar__fill" style={{ width: 30 }} />
              </span>
              Bar and value; below 0.60 the bar is coral and the value in red text
            </li>
          )}
          {lens === "work_type" &&
            WORK_TYPES.map((type) => (
              <li key={type}>
                <WorkTypeGlyph type={type} />
              </li>
            ))}
          {lens === "exceptions" && (
            <>
              <li>
                <span className="mono">Usual route</span>&nbsp;what happens in most cases
              </li>
              <li>
                <span className="mono">Exception</span>&nbsp;on the route taken when a check fails (the line into it says when)
              </li>
              <li>
                <span className="mono">Variation</span>&nbsp;another way of working, under a condition the SME gave
              </li>
              <li>
                <span className="mono">Workaround</span>&nbsp;work done another way, with the SME&apos;s reason (details in Registers,
                Exceptions and workarounds)
              </li>
            </>
          )}
          {lens === "time" && (
            <>
              <li>
                <span className="map-bar__work" style={{ width: 16 }} aria-hidden="true" />
                Work (solid)
              </li>
              <li>
                <span className="map-bar__wait" style={{ width: 16 }} aria-hidden="true" />
                Wait (hatched)
              </li>
              <li>
                <span className="mono">20 + 5</span>&nbsp;minutes of work + wait
              </li>
            </>
          )}
        </ul>
      )}
    </div>
  );
}
