import { useState } from "react";
import { IMAGE_NOTE, imageFileUrl, imageTypeLabel, type WalkthroughCard } from "../../lib/images";

export interface WalkthroughStripProps {
  cards: readonly WalkthroughCard[];
  selectedId: string | null;
  onSelect: (elementId: string) => void;
}

/** A picture, or a striped placeholder naming its type when the picture can't be shown. */
function Picture({ card }: { card: WalkthroughCard }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <span className="walkthrough__placeholder">
        <span className="walkthrough__placeholder-text">{imageTypeLabel(card.image.image_type)}</span>
      </span>
    );
  }
  return (
    <img
      className="walkthrough__img"
      src={imageFileUrl(card.image.id, true)}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

/**
 * The visual walkthrough strip (PRD §5.7.11): 200 px cards in process order, each a picture,
 * "Step n · name" and the caption; the selected step's card has an ink border. Each card is a
 * button that selects its step. Hidden when there are no pictures to walk through.
 */
export function WalkthroughStrip({ cards, selectedId, onSelect }: WalkthroughStripProps) {
  if (cards.length === 0) return null;
  return (
    <section className="walkthrough" aria-label="Visual walkthrough">
      <h2 className="walkthrough__title">
        Visual walkthrough <span className="walkthrough__note">· {IMAGE_NOTE}</span>
      </h2>
      <ul className="walkthrough__list">
        {cards.map((card) => {
          const selected = card.elementId === selectedId;
          return (
            <li key={card.image.id}>
              <button
                type="button"
                className={["walkthrough__card", selected ? "walkthrough__card--selected" : ""].filter(Boolean).join(" ")}
                aria-pressed={selected}
                onClick={() => onSelect(card.elementId)}
              >
                <Picture card={card} />
                <span className="walkthrough__step">
                  Step {card.stepNumber} · {card.stepName}
                </span>{" "}
                <span className="walkthrough__caption">{card.image.caption}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
