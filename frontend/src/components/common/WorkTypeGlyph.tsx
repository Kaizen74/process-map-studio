import type { WorkType } from "../../lib/mapTypes";
import { WORK_TYPE_LABELS } from "../../lib/lens";
import "./common.css";

export interface WorkTypeGlyphProps {
  type: WorkType;
  /** Still Claude's proposal (§3.12.4): "proposed" in muted text until Eric confirms. */
  proposed?: boolean;
}

/** The glyph for a kind of work (PRD §5.5): its shape, then its word, never colour alone. */
function Shape({ type }: { type: WorkType }) {
  switch (type) {
    case "clear":
      return <rect x="2" y="2" width="8" height="8" className="tone-ink" />;
    case "complicated":
      return (
        <>
          <rect x="2" y="2" width="8" height="8" className="tone-ink no-fill" />
          <path d="M2 6 H10" className="tone-ink" />
        </>
      );
    case "complex":
      return (
        <>
          <circle cx="6" cy="6" r="4.5" className="tone-ink no-fill" />
          <circle cx="6" cy="6" r="1.4" className="tone-ink" />
        </>
      );
    case "chaotic":
      return <path d="M6 1.5 L10.5 10.5 L1.5 10.5 Z" className="tone-ink no-fill" />;
    case "confused":
      return (
        <text x="6" y="10" textAnchor="middle" className="glyph__mark">
          ?
        </text>
      );
    case "not_classified":
      return <rect x="2" y="2" width="8" height="8" className="tone-neutral" strokeDasharray="2 1.6" />;
  }
}

export function WorkTypeGlyph({ type, proposed = false }: WorkTypeGlyphProps) {
  return (
    <span className="glyph">
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <Shape type={type} />
      </svg>
      {WORK_TYPE_LABELS[type]}
      {proposed && <span className="glyph__muted">proposed</span>}
    </span>
  );
}
