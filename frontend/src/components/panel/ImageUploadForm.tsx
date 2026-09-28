import { useId, type FormEvent } from "react";
import {
  ACCEPT_ATTRIBUTE,
  IMAGE_TYPES,
  PRIVACY_CONFIRM,
  type ImageDetails,
  type ImageErrors,
  type StepImage,
} from "../../lib/images";
import { Button, CheckboxField, SelectField, TextField } from "../common";

export interface ImageUploadFormProps {
  /** Keeping a suggestion: no file to choose; the picture is shown instead. */
  keeping: StepImage | null;
  details: ImageDetails;
  errors: ImageErrors;
  saving: boolean;
  /** A problem that isn't about one field (e.g. the version can't change). */
  problem: string | null;
  onChange: (details: ImageDetails) => void;
  onSave: () => void;
  onCancel: () => void;
}

/**
 * Add a picture to a step, or keep a suggested one (PRD §5.7.7 item 10): file (JPG, PNG or WebP,
 * up to 10 MB), caption, type and the privacy confirmation, all required. Save explains what is
 * missing instead of saving until everything passes; nothing is sent before then.
 */
export function ImageUploadForm({ keeping, details, errors, saving, problem, onChange, onSave, onCancel }: ImageUploadFormProps) {
  const fileId = useId();
  const fileHelpId = useId();
  const fileErrorId = useId();
  const set = <K extends keyof ImageDetails>(key: K, value: ImageDetails[K]) => onChange({ ...details, [key]: value });
  const count = Object.keys(errors).length;

  function submit(event: FormEvent) {
    event.preventDefault();
    onSave();
  }

  return (
    <form className="image-form" onSubmit={submit} noValidate aria-label={keeping ? "Keep suggested picture" : "Add image to this step"}>
      <h4 className="image-form__title">{keeping ? "Keep this suggested picture" : "Add image to this step"}</h4>
      {keeping ? (
        <p className="image-form__from">
          From {keeping.source_name}
          {keeping.page !== null && `, page ${keeping.page}`}. Check it, then give it a type and confirm it is safe to keep.
        </p>
      ) : (
        <div className={["field", errors.file ? "field--invalid" : ""].filter(Boolean).join(" ")}>
          <label className="field__label" htmlFor={fileId}>
            Picture
          </label>
          <input
            id={fileId}
            className="field__control image-form__file"
            type="file"
            accept={ACCEPT_ATTRIBUTE}
            aria-invalid={errors.file ? true : undefined}
            aria-describedby={[fileHelpId, errors.file ? fileErrorId : ""].filter(Boolean).join(" ")}
            onChange={(event) => set("file", event.target.files?.[0] ?? null)}
          />
          <span id={fileHelpId} className="field__help">
            JPG, PNG or WebP, up to 10 MB. Location and camera details are removed when it is saved.
          </span>
          {errors.file && (
            <span id={fileErrorId} className="field__error">
              {errors.file}
            </span>
          )}
        </div>
      )}
      <TextField
        label="Caption"
        value={details.caption}
        onChange={(value) => set("caption", value)}
        help="What the picture shows, using role names, not people's names."
        error={errors.caption ?? null}
      />
      <SelectField
        label="Type of picture"
        value={details.imageType}
        options={[{ value: "", label: "Choose a type" }, ...IMAGE_TYPES]}
        onChange={(value) => set("imageType", value as ImageDetails["imageType"])}
        error={errors.image_type ?? null}
      />
      <CheckboxField
        label={PRIVACY_CONFIRM}
        checked={details.confirmed}
        onChange={(checked) => set("confirmed", checked)}
        error={errors.redaction_confirmed ?? null}
      />
      {count > 0 && (
        <p className="field__error" role="alert">
          {count === 1 ? "One thing to fix" : `${count} things to fix`} before saving.
        </p>
      )}
      {problem && (
        <p className="panel-danger" role="alert">
          {problem}
        </p>
      )}
      <div className="image-form__actions">
        <Button variant="primary" type="submit" aria-busy={saving || undefined}>
          {saving ? "Saving…" : keeping ? "Keep picture" : "Add picture"}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
