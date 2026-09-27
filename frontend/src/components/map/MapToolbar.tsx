import { useState } from "react";
import { LENSES, type Lens } from "../../lib/lens";
import { plural } from "../../lib/format";
import { Button, Popover, SegmentedControl } from "../common";

export type Zoom = "fit" | "full";
export type MapView = "map" | "table";

export interface MapToolbarProps {
  view: MapView;
  onView: (view: MapView) => void;
  lens: Lens;
  onLens: (lens: Lens) => void;
  zoom: Zoom;
  onZoom: (zoom: Zoom) => void;
  steps: number;
  lanes: number;
  phases: number;
  /** Lint L12: more than 25 steps or 6 lanes (constraint 18: warn, don't block). */
  large: boolean;
  /** "Add missing step" in the overflow menu; omitted where the version can't change. */
  onAddStep?: (() => void) | undefined;
  /** "Refresh draft from sources" in the overflow menu; omitted where it isn't offered. */
  onRefresh?: (() => void) | undefined;
}

const VIEWS = [
  { value: "map", label: "Map" },
  { value: "table", label: "Table" },
] as const;

const ZOOMS = [
  { value: "fit", label: "Fit" },
  { value: "full", label: "100%" },
] as const;

/**
 * Map | Table, the lens, Fit | 100% and the map's size (PRD §5.7.3). Lens and zoom apply to the
 * map only, so the table view leaves them out. "Add missing step" and "Refresh draft from sources"
 * sit in the overflow (More).
 */
export function MapToolbar({
  view,
  onView,
  lens,
  onLens,
  zoom,
  onZoom,
  steps,
  lanes,
  phases,
  large,
  onAddStep,
  onRefresh,
}: MapToolbarProps) {
  const [more, setMore] = useState(false);
  const counts = `${plural(steps, "step")} · ${plural(lanes, "lane")} · ${plural(phases, "phase")}`;
  const map = view === "map";
  return (
    <div className="map-toolbar">
      <div className="map-toolbar__group">
        <SegmentedControl label="View" options={VIEWS} value={view} onChange={onView} />
        {map && (
          <>
            <span className="map-toolbar__label" aria-hidden="true">
              Lens
            </span>
            <SegmentedControl label="Lens" options={LENSES} value={lens} onChange={onLens} />
          </>
        )}
      </div>
      <div className="map-toolbar__group">
        <span className={large ? "map-toolbar__counts map-toolbar__counts--large" : "map-toolbar__counts"}>
          {large ? `${counts}. Large map: consider splitting by phase` : counts}
        </span>
        {map && <SegmentedControl label="Zoom" options={ZOOMS} value={zoom} onChange={onZoom} />}
        {(onAddStep || onRefresh) && (
          <div className="popover-anchor">
            <Button aria-expanded={more} onClick={() => setMore(!more)}>
              More
            </Button>
            <Popover open={more} title="More" align="end" onClose={() => setMore(false)}>
              <div className="map-toolbar__menu">
                {onAddStep && (
                  <Button
                    onClick={() => {
                      setMore(false);
                      onAddStep();
                    }}
                  >
                    Add missing step
                  </Button>
                )}
                {onRefresh && (
                  <Button
                    onClick={() => {
                      setMore(false);
                      onRefresh();
                    }}
                  >
                    Refresh draft from sources
                  </Button>
                )}
              </div>
            </Popover>
          </div>
        )}
      </div>
    </div>
  );
}
