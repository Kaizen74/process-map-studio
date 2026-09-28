// Pictures on steps (API_CONTRACT.md → Images; PRD §5.7.7 item 10, §5.7.11, constraint 11). In
// lib so that components can type their props and build a picture's address without src/api.

export type ImageType =
  | "workplace_photo"
  | "system_screenshot"
  | "executed_artefact"
  | "illustrative_diagram"
  | "document_extract";

export interface StepImage {
  id: string;
  element_id: string | null;
  caption: string;
  image_type: ImageType | null;
  origin: "uploaded" | "extracted";
  status: "suggested" | "kept" | "discarded";
  redaction_confirmed: boolean;
  /** For a picture suggested from a PDF: the file and page it came from; else "" and null. */
  source_name: string;
  page: number | null;
  created_at: string;
}

/** B.16 image types, in plain words. */
export const IMAGE_TYPES: readonly { value: ImageType; label: string }[] = [
  { value: "workplace_photo", label: "Workplace photo" },
  { value: "system_screenshot", label: "System screenshot" },
  { value: "executed_artefact", label: "Completed form or record" },
  { value: "illustrative_diagram", label: "Illustrative diagram" },
  { value: "document_extract", label: "Extract from a document" },
];

export function imageTypeLabel(type: ImageType | null): string {
  return IMAGE_TYPES.find((t) => t.value === type)?.label ?? "Type not chosen yet";
}

/** Where the app serves a picture (or its thumbnail). Never linked from any export. */
export function imageFileUrl(imageId: string, thumb = false): string {
  return `/api/images/${encodeURIComponent(imageId)}/file${thumb ? "?size=thumb" : ""}`;
}

export const IMAGE_NOTE = "In-app only · never exported · metadata stripped";
export const PRIVACY_CONFIRM = "Faces, names, badge numbers and flight identifiers are removed or not shown";

export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const ACCEPTED = new Set(["image/jpeg", "image/png", "image/webp"]);
const ACCEPTED_NAME = /\.(jpe?g|png|webp)$/i;
export const ACCEPT_ATTRIBUTE = ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp";

/** What Eric fills in to add a picture, or to keep a suggested one (no file then). */
export interface ImageDetails {
  file: File | null;
  caption: string;
  imageType: ImageType | "";
  confirmed: boolean;
}

export type ImageField = "file" | "caption" | "image_type" | "redaction_confirmed";
export type ImageErrors = Partial<Record<ImageField, string>>;

// The same words the server uses (API_CONTRACT.md → POST /api/elements/{eid}/images).
export const IMAGE_MESSAGES = {
  wrongType: "Choose a JPG, PNG or WebP picture.",
  tooBig: "Pictures can be up to 10 MB.",
  caption: "Add a caption of up to 300 characters.",
  imageType: "Choose what kind of picture this is.",
  confirm: "Confirm that faces, names, badge numbers and flight identifiers are removed or not shown.",
} as const;

/** Everything missing or wrong before anything is sent; an empty object means ready to save. */
export function checkImageDetails(details: ImageDetails, needFile: boolean): ImageErrors {
  const errors: ImageErrors = {};
  if (needFile) {
    const file = details.file;
    if (!file || !(ACCEPTED.has(file.type) || ACCEPTED_NAME.test(file.name))) errors.file = IMAGE_MESSAGES.wrongType;
    else if (file.size > MAX_IMAGE_BYTES) errors.file = IMAGE_MESSAGES.tooBig;
  }
  const caption = details.caption.trim();
  if (!caption || caption.length > 300 || /[\r\n]/.test(caption)) errors.caption = IMAGE_MESSAGES.caption;
  if (!details.imageType) errors.image_type = IMAGE_MESSAGES.imageType;
  if (!details.confirmed) errors.redaction_confirmed = IMAGE_MESSAGES.confirm;
  return errors;
}

export const EMPTY_DETAILS: ImageDetails = { file: null, caption: "", imageType: "", confirmed: false };

/** One card of the walkthrough strip (PRD §5.7.11). */
export interface WalkthroughCard {
  image: StepImage;
  elementId: string;
  /** Position among the steps (start and end not counted), from 1. */
  stepNumber: number;
  stepName: string;
}

const STEP_KINDS = new Set(["activity", "decision", "approval"]);

/**
 * The strip's cards: kept pictures only (a suggestion joins once kept, PRD §5.8), in process
 * order, which is the order of the graph's elements. Pictures on rejected steps are left out.
 */
export function walkthroughCards(
  elements: readonly { id: string; kind: string; label: string; review_status: string }[],
  images: readonly StepImage[],
): WalkthroughCard[] {
  const steps = elements.filter((e) => STEP_KINDS.has(e.kind) && e.review_status !== "rejected");
  const number = new Map(steps.map((e, i) => [e.id, i + 1]));
  const name = new Map(steps.map((e) => [e.id, e.label]));
  return images
    .filter((image) => image.status === "kept" && number.has(image.element_id ?? ""))
    .map((image) => {
      const id = image.element_id ?? "";
      return { image, elementId: id, stepNumber: number.get(id) ?? 0, stepName: name.get(id) ?? "" };
    })
    .sort((a, b) => a.stepNumber - b.stepNumber);
}

/** The steps that show the has-images marker: any picture that isn't discarded. */
export function stepsWithImages(images: readonly StepImage[]): Set<string> {
  return new Set(images.filter((i) => i.status !== "discarded" && i.element_id).map((i) => i.element_id ?? ""));
}
