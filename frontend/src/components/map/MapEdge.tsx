import type { LayoutEdge } from "../../lib/mapTypes";
import { arrowhead, edgeSegments } from "../../lib/edges";
import { placedChip } from "./placement";

export interface MapEdgeProps {
  edge: LayoutEdge;
  /** Touches the selected step: drawn in ink, 2 px (PRD §5.5). */
  active: boolean;
  /** Touches a rejected step: faded with it. */
  faded: boolean;
}

/** One orthogonal line: bordered segments, a CSS-triangle arrowhead and its label chip. */
export function MapEdge({ edge, active, faded }: MapEdgeProps) {
  const tip = arrowhead(edge.points);
  const classes = [
    "map-edge",
    edge.is_back_edge && "map-edge--back",
    active && "map-edge--active",
    faded && "map-faded",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={classes} data-edge={edge.id} data-kind={edge.kind}>
      {edgeSegments(edge.points).map((s, i) => (
        <span
          key={i}
          className={`map-edge__segment map-edge__segment--${s.orientation}`}
          style={
            s.orientation === "horizontal"
              ? { left: s.x, top: s.y, width: s.length }
              : { left: s.x, top: s.y, height: s.length }
          }
        />
      ))}
      {tip && (
        <span className={`map-edge__arrow map-edge__arrow--${tip.direction}`} style={{ left: tip.x, top: tip.y }} />
      )}
      {edge.label && edge.label_pos && (
        <span className="map-edge__label" style={placedChip(edge.label_pos)}>
          {edge.label}
        </span>
      )}
    </div>
  );
}
