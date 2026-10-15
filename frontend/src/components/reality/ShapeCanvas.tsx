import { useId } from "react";
import type { Shape, ShapeGeometry } from "../../lib/reality";
import "./reality.css";

export interface ShapeCanvasProps {
  geometry: ShapeGeometry;
  label: string;
  selected: string | null;
  onSelect: (code: string) => void;
}

const LINE = 16;
const FIRST_LINE = 12;
const PAD = 4;

/** The shape's classes: its role, its line style and, on a discrepancy, its impact class. */
function classes(shape: Shape): string {
  const out = [`rs rs--${shape.role}`, `line--${shape.style}`];
  if (shape.impact_class) out.push(`rs-impact--${shape.impact_class}`);
  return out.join(" ");
}

function ShapeElement({ shape, hatch }: { shape: Shape; hatch: string }) {
  const className = classes(shape);
  switch (shape.kind) {
    case "rect":
      return (
        <>
          <rect
            className={className}
            x={shape.x}
            y={shape.y}
            width={shape.width}
            height={shape.height}
            rx={shape.role === "markup-wait" ? shape.height / 2 : 3}
            style={shape.role === "wait" ? { fill: `url(#${hatch})` } : undefined}
          />
          {(shape.role === "markup-added" || shape.role === "legend-added") && (
            <text className="rs-glyph" x={shape.x + shape.width / 2} y={shape.y + shape.height - 4} textAnchor="middle">
              +
            </text>
          )}
        </>
      );
    case "circle":
      return <circle className={className} cx={shape.x} cy={shape.y} r={shape.r} />;
    case "line":
      return <line className={className} x1={shape.x} y1={shape.y} x2={shape.x2} y2={shape.y2} />;
    case "path":
      return <path className={className} d={shape.path} />;
    case "text":
      return (
        <text className={className} x={shape.x + PAD} y={shape.y + FIRST_LINE}>
          {shape.lines.map((line, i) => (
            <tspan key={i} x={shape.x + PAD} dy={i === 0 ? 0 : LINE}>
              {line}
            </tspan>
          ))}
        </text>
      );
    default:
      return null;
  }
}

/**
 * The P13c views (Redline, Where the time goes, Belief vs evidence, Typical case) as the backend
 * placed them: every shape's position, size and words come from the snapshot; this draws them
 * and nothing else (constraint 20). Shapes carrying an X code dim when another code is selected.
 */
export function ShapeCanvas({ geometry, label, selected, onSelect }: ShapeCanvasProps) {
  const hatch = `rs-hatch-${useId().replace(/:/g, "")}`;
  return (
    <svg className="reality-canvas" viewBox={`0 0 ${geometry.width} ${geometry.height}`} role="img" aria-label={label}>
      <defs>
        <pattern id={hatch} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect className="rs-hatch-ground" width="6" height="6" />
          <line className="rs-hatch-line" x1="0" y1="0" x2="0" y2="6" />
        </pattern>
      </defs>
      {geometry.shapes.map((shape, i) => {
        const code = shape.code;
        const dimmed = selected !== null && code !== null && code !== selected;
        return (
          <g
            key={i}
            className={dimmed ? "is-dimmed" : undefined}
            data-role={shape.role}
            onClick={code ? () => onSelect(code) : undefined}
          >
            <ShapeElement shape={shape} hatch={hatch} />
          </g>
        );
      })}
    </svg>
  );
}
