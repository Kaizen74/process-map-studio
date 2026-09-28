import { glyphFor, type GlyphShape, type StanceOrState } from "../../lib/stateGlyph";
import "./common.css";

export interface StateGlyphProps {
  state: StanceOrState;
  /** Show the text label next to the glyph (default). When false, the label is the accessible name. */
  showLabel?: boolean;
}

function Shape({ shape, tone }: { shape: GlyphShape; tone: string }) {
  const toneClass = `tone-${tone}`;
  switch (shape) {
    case "filled-circle":
      return <circle cx="6" cy="6" r="4.5" className={toneClass} />;
    case "dashed-ring":
      return <circle cx="6" cy="6" r="4.5" className={toneClass} strokeDasharray="2 1.6" />;
    case "open-ring":
      return <circle cx="6" cy="6" r="4.5" className={`${toneClass} no-fill`} strokeWidth="1.5" />;
    case "left-half":
      return (
        <>
          <circle cx="6" cy="6" r="4.5" className={`${toneClass} no-fill`} />
          <path d="M6 1.5 A4.5 4.5 0 0 0 6 10.5 Z" className={toneClass} />
        </>
      );
    case "right-half":
      return (
        <>
          <circle cx="6" cy="6" r="4.5" className={`${toneClass} no-fill`} />
          <path d="M6 1.5 A4.5 4.5 0 0 1 6 10.5 Z" className={toneClass} />
        </>
      );
    case "ring-cross":
      return (
        <>
          <circle cx="6" cy="6" r="4.5" className={`${toneClass} no-fill`} strokeWidth="1.5" />
          <path d="M3.8 3.8 L8.2 8.2 M8.2 3.8 L3.8 8.2" className={toneClass} strokeWidth="1.5" />
        </>
      );
    case "outlined-square":
      return <rect x="1.75" y="1.75" width="8.5" height="8.5" className={toneClass} />;
    case "dash":
      return <path d="M2.5 6 H9.5" className={toneClass} strokeWidth="1.5" />;
  }
}

/** Source stance or state as shape plus text (PRD §5.2); never colour alone. */
export function StateGlyph({ state, showLabel = true }: StateGlyphProps) {
  const spec = glyphFor(state);
  const classes = ["glyph", spec.dangerText && "glyph--danger-text"].filter(Boolean).join(" ");
  return (
    <span className={classes} data-shape={spec.shape}>
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
        <Shape shape={spec.shape} tone={spec.tone} />
      </svg>
      {showLabel ? <span>{spec.label}</span> : <span className="visually-hidden">{spec.label}</span>}
    </span>
  );
}
