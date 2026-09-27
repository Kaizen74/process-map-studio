import type { EvidenceCard as EvidenceCardData } from "../../lib/mapTypes";
import { SOURCE_KINDS } from "../../lib/panelText";
import { StateGlyph } from "../common";

export interface EvidenceCardProps {
  card: EvidenceCardData;
  onOpen: (card: EvidenceCardData) => void;
}

const SILENCE = "No passage in this source addresses the step. Silence is not contradiction.";

/**
 * One piece of evidence (PRD §5.7.7): stance glyph and word, source, anchor, the quote and any
 * divergence detail. A cited passage opens the source viewer; a silent source is grey and not
 * clickable.
 */
export function EvidenceCard({ card, onOpen }: EvidenceCardProps) {
  const kind = SOURCE_KINDS[card.source_kind] ?? "Document";
  const head = (
    <span className="evidence__head">
      <StateGlyph state={card.stance} />
      <span className="evidence__source">
        {kind} · {card.source_name}
      </span>
      {card.anchor && <span className="evidence__anchor mono">{card.anchor}</span>}
    </span>
  );
  if (card.stance === "silent" || !card.segment_id) {
    return (
      <div className="evidence evidence--silent">
        {head}
        <span className="evidence__silence">{SILENCE}</span>
      </div>
    );
  }
  return (
    <button
      type="button"
      className={card.stance === "contradicts" ? "evidence evidence--contradicts" : "evidence"}
      onClick={() => onOpen(card)}
      aria-label={`Open ${card.source_name} at ${card.anchor}: ${card.stance === "supports" ? "supports" : "contradicts"} the step`}
    >
      {head}
      {card.quote && <span className="evidence__quote">“{card.quote}”</span>}
      {card.note && <span className="evidence__note">{card.note}</span>}
    </button>
  );
}
