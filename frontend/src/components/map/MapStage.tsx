import type { ExceptionStep } from "../../lib/exceptions";
import type { Graph, Layout } from "../../lib/mapTypes";
import { lensLine, longestStep, markersFor, nodeName, type Lens } from "../../lib/lens";
import { ghostLabel, type AsView } from "../../lib/views";
import { MapEdge } from "./MapEdge";
import { MapNode } from "./MapNode";
import "./map.css";

export interface MapStageProps {
  graph: Graph;
  layout: Layout;
  lens: Lens;
  /** The view drawn (§3.12.11): it picks the variant values the lens line shows. */
  view?: AsView;
  /** 1 = 100%; the stage is scaled from the top-left (PRD §5.5). */
  scale: number;
  selectedId: string | null;
  onSelect: (elementId: string) => void;
  /** Steps with a picture that isn't discarded: the has-images marker (PRD §5.5). */
  withImages?: ReadonlySet<string>;
  /** The Exceptions lens: each step's route in this view, from the backend (X2). */
  routes?: ReadonlyMap<string, ExceptionStep>;
}

/**
 * The swimlane map drawn exactly where the backend layout puts everything (PRD §3.9, §5.5):
 * lanes, phase band, orthogonal lines and nodes as absolutely positioned HTML. The UI never
 * computes layout. Nodes are buttons in process order, so Tab follows the process.
 */
export function MapStage({
  graph,
  layout,
  lens,
  view = "done",
  scale,
  selectedId,
  onSelect,
  withImages,
  routes,
}: MapStageProps) {
  const elements = new Map(graph.elements.map((e) => [e.id, e]));
  const roles = new Map(graph.roles.map((r) => [r.id, r.name]));
  const edgesById = new Map(graph.edges.map((e) => [e.id, e]));
  const rejected = new Set(graph.elements.filter((e) => e.review_status === "rejected").map((e) => e.id));
  const longest = longestStep(graph.elements);
  const { w, h } = layout.canvas;
  const bandEnd = layout.lanes[0]?.y ?? h;

  return (
    <div className="map-viewport" style={{ width: w * scale, height: h * scale }}>
      <div className="map-stage" style={{ width: w, height: h, transform: `scale(${scale})` }}>
        <div className="map-band" style={{ height: bandEnd }} aria-hidden="true">
          <span className="map-band__heading">
            Phase
          </span>
          {layout.phases.map((p) => (
            <span key={p.phase_id} className="map-band__phase" style={{ left: p.x, width: p.w }}>
              <span className="map-band__name">{p.label}</span>
              {p.time_window && <span className="map-band__window mono">{p.time_window}</span>}
            </span>
          ))}
        </div>
        {layout.lanes.map((lane, i) => (
          <div
            key={lane.role_id || `lane-${i}`}
            role="group"
            aria-label={`${lane.label || "No lane"} lane, ${lane.step_count} ${lane.step_count === 1 ? "step" : "steps"}`}
            className={i % 2 === 0 ? "map-lane" : "map-lane map-lane--even"}
            style={{ top: lane.y, height: lane.h, width: w }}
          >
            <div className="map-lane__label" aria-hidden="true">
              <span className="map-lane__name">{lane.label || "No lane"}</span>
              <span className="map-lane__count">
                {lane.step_count} {lane.step_count === 1 ? "step" : "steps"}
              </span>
            </div>
          </div>
        ))}
        {layout.phases.slice(1).map((p) => (
          <span key={p.phase_id} className="map-divider" style={{ left: p.x, height: h }} aria-hidden="true" />
        ))}
        <div className="map-edges" aria-hidden="true">
          {layout.edges.map((edge) => {
            const g = edgesById.get(edge.id);
            const touches = (id: string | undefined) => id !== undefined && (id === g?.from || id === g?.to);
            return (
              <MapEdge
                key={edge.id}
                edge={edge}
                active={selectedId !== null && touches(selectedId)}
                faded={[...rejected].some((id) => touches(id))}
              />
            );
          })}
        </div>
        {layout.nodes.map((node) => {
          const element = elements.get(node.id);
          if (!element) return null;
          const hasImages = withImages?.has(node.id) ?? false;
          const base = nodeName(element, roles.get(element.lane_role_id ?? "") ?? "");
          // A ghosted step (Show the other view) says where it belongs, in the lens line's place.
          const name = node.ghost ? `${base}, ${ghostLabel(view)}` : base;
          return (
            <MapNode
              key={node.id}
              element={element}
              node={node}
              name={hasImages ? `${name}, has images` : name}
              markers={node.ghost ? [] : markersFor(element, { hasImages })}
              lens={
                node.ghost
                  ? { kind: "text", text: ghostLabel(view), danger: false }
                  : lensLine(element, lens, longest, view, routes)
              }
              selected={node.id === selectedId}
              onSelect={onSelect}
            />
          );
        })}
      </div>
    </div>
  );
}
