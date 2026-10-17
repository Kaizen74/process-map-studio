import type { CodeView, GlanceView } from "../../lib/reality";
import "./reality.css";

export interface GlanceProps {
  view: GlanceView;
  codes: readonly CodeView[];
  selected: string | null;
  onSelect: (code: string) => void;
}

/**
 * RV1 Glance (PRD §5.12.3): the grey trunk (the manual) fracturing into one ribbon per route,
 * width = share. Drawn from the backend geometry only.
 */
export function Glance({ view, codes, selected, onSelect }: GlanceProps) {
  const g = view.geometry;
  const routes = new Map(view.glance.routes.map((r) => [r.id, r]));
  const impact = new Map(codes.map((c) => [c.code, c.impact_class]));
  return (
    <svg
      className="reality-canvas"
      viewBox={`0 0 ${g.width} ${g.height}`}
      role="img"
      aria-label={`${view.title} ${view.headline}`}
    >
      <line
        className="glance-trunk"
        x1={g.trunk.x1}
        x2={g.trunk.x2}
        y1={g.trunk.y}
        y2={g.trunk.y}
        strokeWidth={g.trunk.width}
      />
      <text className="reality-label" x={g.trunk.x1} y={g.trunk.y - g.trunk.width / 2 - 10}>
        The manual
      </text>
      {g.ribbons.map((ribbon) => {
        const route = routes.get(ribbon.route_id);
        if (!route) return null;
        const own = route.codes;
        const dimmed = selected !== null && !own.includes(selected);
        const tone = route.documented ? "documented" : (route.impact_class ?? "neutral");
        return (
          <g key={ribbon.route_id} className={dimmed ? "is-dimmed" : undefined}>
            <path
              className={`glance-ribbon glance-ribbon--${tone} line--${ribbon.style}`}
              d={ribbon.path}
              strokeWidth={ribbon.width}
              onClick={() => own[0] && onSelect(own[0])}
            />
            <text className="reality-label" x={ribbon.label_x} y={ribbon.label_y + 4}>
              <tspan className="reality-label--strong">{route.share.text}</tspan> {route.name}
              {own.map((c) => (
                <tspan key={c} className={`reality-code reality-code--${impact.get(c) ?? "neutral"}`}>
                  {" "}
                  {c}
                </tspan>
              ))}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
