import type { Mark, StackView } from "../../lib/reality";
import { canvasWidth } from "../../lib/reality";
import "./reality.css";

export interface RealityStackProps {
  view: StackView;
  selected: string | null;
  onSelect: (code: string) => void;
}

const LINE = 16;

function markClass(mark: Mark): string {
  const base = `stack-mark stack-mark--${mark.kind}`;
  if (mark.kind === "branch" && mark.impact_class) return `${base} stack-mark--${mark.impact_class}`;
  return base;
}

/**
 * RV2 Reality stack (PRD §5.12.3): five bands on the shared columns, from what we promise to
 * what it costs; one X-ray lens on the column losing most. Drawn from the backend geometry only.
 */
export function RealityStack({ view, selected, onSelect }: RealityStackProps) {
  const g = view.geometry;
  return (
    <svg className="reality-canvas" style={canvasWidth(g.width)} viewBox={`0 0 ${g.width} ${g.height}`} role="img" aria-label={`${view.title} ${view.headline}`}>
      {g.bands.map((b) => (
        <rect key={b.id} className={`stack-band stack-band--${b.id}`} x={b.x} y={b.y} width={b.width} height={b.height} />
      ))}
      {g.lens && (
        <g className="stack-lens">
          <rect x={g.lens.x} y={g.lens.y} width={g.lens.width} height={g.lens.height} />
          <text className="reality-label reality-label--strong" x={g.lens.label_x} y={g.lens.label_y}>
            {view.stack.lens?.label}
          </text>
        </g>
      )}
      {g.band_labels.map((l) => (
        <text key={l.id} className="reality-label" x={l.x} y={l.y}>
          {l.lines.map((line, i) => (
            <tspan key={i} x={l.x} dy={i === 0 ? 0 : LINE} className={i === 0 ? "reality-label--strong" : undefined}>
              {line}
            </tspan>
          ))}
        </text>
      ))}
      {g.column_labels.map((l) => (
        <text key={l.id} className="reality-label reality-label--strong" x={l.x} y={l.y}>
          {l.lines[0]}
        </text>
      ))}
      {g.marks.map((m, i) => {
        const dimmed = selected !== null && m.code !== selected && m.kind === "branch";
        return (
          <g
            key={`${m.band_id}-${m.column_id}-${i}`}
            className={dimmed ? "is-dimmed" : undefined}
            onClick={m.code ? () => onSelect(m.code ?? "") : undefined}
          >
            <rect className={`${markClass(m)} line--${m.style}`} x={m.x} y={m.y} width={m.width} height={m.height} rx="6" />
            <text className={`stack-text stack-text--${m.kind}`} x={m.x + 8} y={m.y + 15}>
              {m.lines.map((line, n) => (
                <tspan key={n} x={m.x + 8} dy={n === 0 ? 0 : LINE}>
                  {line}
                </tspan>
              ))}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
