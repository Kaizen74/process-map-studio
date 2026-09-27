import { LENSES, type Lens } from "../../lib/lens";
import { plural } from "../../lib/format";
import { SegmentedControl } from "../common";

export type Zoom = "fit" | "full";

export interface MapToolbarProps {
  lens: Lens;
  onLens: (lens: Lens) => void;
  zoom: Zoom;
  onZoom: (zoom: Zoom) => void;
  steps: number;
  lanes: number;
  phases: number;
  /** Lint L12: more than 25 steps or 6 lanes (constraint 18: warn, don't block). */
  large: boolean;
}

const ZOOMS = [
  { value: "fit", label: "Fit" },
  { value: "full", label: "100%" },
] as const;

/** Lens, Fit | 100% and the map's size (PRD §5.7.3). The table view arrives in P6. */
export function MapToolbar({ lens, onLens, zoom, onZoom, steps, lanes, phases, large }: MapToolbarProps) {
  const counts = `${plural(steps, "step")} · ${plural(lanes, "lane")} · ${plural(phases, "phase")}`;
  return (
    <div className="map-toolbar">
      <div className="map-toolbar__group">
        <span className="map-toolbar__label" aria-hidden="true">
          Lens
        </span>
        <SegmentedControl label="Lens" options={LENSES} value={lens} onChange={onLens} />
      </div>
      <div className="map-toolbar__group">
        <span className={large ? "map-toolbar__counts map-toolbar__counts--large" : "map-toolbar__counts"}>
          {large ? `${counts}. Large map: consider splitting by phase` : counts}
        </span>
        <SegmentedControl label="Zoom" options={ZOOMS} value={zoom} onChange={onZoom} />
      </div>
    </div>
  );
}
