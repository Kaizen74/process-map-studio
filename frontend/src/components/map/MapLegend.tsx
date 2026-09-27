import type { Lens } from "../../lib/lens";
import type { StanceOrState } from "../../lib/stateGlyph";
import { StateGlyph } from "../common";

const STATES: StanceOrState[] = ["corroborated", "documented_only", "practiced_only", "contested", "trace_contradicted"];

/** Always under the map (PRD §5.5): shapes, markers and lines, plus the active lens's key. */
export function MapLegend({ lens }: { lens: Lens }) {
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
