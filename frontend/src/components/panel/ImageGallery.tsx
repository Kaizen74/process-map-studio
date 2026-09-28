import { imageFileUrl, imageTypeLabel, type StepImage } from "../../lib/images";
import { Button } from "../common";

export interface ImageGalleryProps {
  images: readonly StepImage[];
  /** Published versions: no Keep, Discard or Remove. */
  readOnly: boolean;
  /** The picture being kept, discarded or removed right now. */
  busyId: string | null;
  onKeep: (image: StepImage) => void;
  onDiscard: (image: StepImage) => void;
  onRemove: (image: StepImage) => void;
}

/**
 * Section 10's two-column gallery (PRD §5.7.7 item 10). A suggested picture has a dashed border,
 * the word "Suggested" and where it came from; Keep and Discard on a draft. An uploaded one has
 * Remove on a draft. Thumbnails only; the caption is the picture's text alternative.
 */
export function ImageGallery({ images, readOnly, busyId, onKeep, onDiscard, onRemove }: ImageGalleryProps) {
  return (
    <ul className="image-gallery" aria-label="Pictures on this step">
      {images.map((image) => {
        const suggested = image.status === "suggested";
        const busy = busyId === image.id;
        return (
          <li
            key={image.id}
            className={["image-card", suggested ? "image-card--suggested" : ""].filter(Boolean).join(" ")}
            aria-busy={busy || undefined}
          >
            <figure className="image-card__figure">
              <img className="image-card__img" src={imageFileUrl(image.id, true)} alt={image.caption} loading="lazy" />
              <figcaption className="image-card__caption">{image.caption}</figcaption>
            </figure>
            <p className="image-card__meta">
              {suggested ? (
                <>
                  <span className="image-card__tag">Suggested</span> from {image.source_name}
                  {image.page !== null && `, page ${image.page}`}
                </>
              ) : (
                imageTypeLabel(image.image_type)
              )}
            </p>
            {!readOnly && suggested && (
              <div className="image-card__actions">
                <Button variant="secondary" onClick={() => onKeep(image)} aria-label={`Keep ${image.caption}`}>
                  Keep
                </Button>
                <Button variant="link" onClick={() => onDiscard(image)} aria-label={`Discard ${image.caption}`}>
                  {busy ? "Discarding…" : "Discard"}
                </Button>
              </div>
            )}
            {!readOnly && image.origin === "uploaded" && (
              <div className="image-card__actions">
                <Button variant="link" onClick={() => onRemove(image)} aria-label={`Remove ${image.caption}`}>
                  Remove
                </Button>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
