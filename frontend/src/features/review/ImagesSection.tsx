import { useState } from "react";
import { Button, Dialog, ErrorState, Skeleton } from "../../components/common";
import { ImageGallery, ImageUploadForm, PanelSection } from "../../components/panel";
import { useToast } from "../../components/shell";
import { useImageChanges, useStepImages } from "../../hooks/useImages";
import { copyDetailsOf, fieldOf, messageOf } from "../../lib/errors";
import {
  EMPTY_DETAILS,
  IMAGE_NOTE,
  checkImageDetails,
  type ImageDetails,
  type ImageErrors,
  type ImageField,
  type StepImage,
} from "../../lib/images";

export interface ImagesSectionProps {
  elementId: string;
  versionId: string;
  engagementId: string;
  /** False on a published version: pictures are shown, nothing changes. */
  editable: boolean;
}

const FIELDS = new Set<string>(["file", "caption", "image_type", "redaction_confirmed"]);

/** The panel's Images section (PRD §5.7.7 item 10): gallery, Keep/Discard, Remove, Add image. */
export function ImagesSection({ elementId, versionId, engagementId, editable }: ImagesSectionProps) {
  const images = useStepImages(elementId);
  const { upload, change, remove } = useImageChanges(elementId, versionId, engagementId);
  const toast = useToast();
  // The form: null when closed; `keeping` set when it keeps a suggestion rather than adds.
  const [form, setForm] = useState<{ keeping: StepImage | null; details: ImageDetails } | null>(null);
  const [errors, setErrors] = useState<ImageErrors>({});
  const [problem, setProblem] = useState<string | null>(null);
  const [removing, setRemoving] = useState<StepImage | null>(null);

  function open(keeping: StepImage | null) {
    upload.reset();
    change.reset();
    setErrors({});
    setProblem(null);
    setForm({ keeping, details: keeping ? { ...EMPTY_DETAILS, caption: keeping.caption } : EMPTY_DETAILS });
  }

  function refused(error: unknown) {
    const field = fieldOf(error);
    if (field && FIELDS.has(field)) setErrors({ [field as ImageField]: messageOf(error) });
    else setProblem(messageOf(error));
  }

  function save() {
    if (!form) return;
    const found = checkImageDetails(form.details, form.keeping === null);
    setErrors(found);
    setProblem(null);
    if (Object.keys(found).length > 0) return;
    const { keeping, details } = form;
    const done = (message: string) => () => {
      setForm(null);
      toast(message);
    };
    if (keeping) {
      change.mutate(
        {
          imageId: keeping.id,
          body: {
            status: "kept",
            caption: details.caption.trim(),
            ...(details.imageType ? { image_type: details.imageType } : {}),
            redaction_confirmed: true,
          },
        },
        { onSuccess: done("Suggested picture kept."), onError: refused },
      );
    } else {
      upload.mutate(details, { onSuccess: done("Picture added. Location and camera details were removed."), onError: refused });
    }
  }

  function discard(image: StepImage) {
    change.mutate(
      { imageId: image.id, body: { status: "discarded" } },
      { onSuccess: () => toast("Suggested picture discarded."), onError: (error) => setProblem(messageOf(error)) },
    );
  }

  function confirmRemove() {
    if (!removing) return;
    const image = removing;
    remove.mutate(image.id, {
      onSuccess: () => {
        setRemoving(null);
        toast("Picture removed.");
      },
    });
  }

  const list = images.data ?? [];
  const busyId = change.isPending ? (change.variables?.imageId ?? null) : null;
  return (
    <PanelSection title="Images" note={IMAGE_NOTE}>
      {images.isPending && (
        <div className="image-gallery" aria-busy="true">
          <Skeleton height="120px" />
          <Skeleton height="120px" />
        </div>
      )}
      {images.isError && (
        <ErrorState
          title="The pictures couldn't be loaded"
          message={messageOf(images.error)}
          details={copyDetailsOf(images.error)}
          onRetry={() => void images.refetch()}
        />
      )}
      {images.isSuccess && list.length === 0 && (
        <p className="inline-note">{editable ? "No pictures on this step yet." : "No pictures on this step."}</p>
      )}
      {list.length > 0 && (
        <ImageGallery
          images={list}
          readOnly={!editable}
          busyId={busyId}
          onKeep={(image) => open(image)}
          onDiscard={discard}
          onRemove={(image) => {
            remove.reset();
            setRemoving(image);
          }}
        />
      )}
      {problem && !form && (
        <p className="panel-danger" role="alert">
          {problem}
        </p>
      )}
      {editable && form && (
        <ImageUploadForm
          keeping={form.keeping}
          details={form.details}
          errors={errors}
          saving={upload.isPending || change.isPending}
          problem={problem}
          onChange={(details) => setForm({ ...form, details })}
          onSave={save}
          onCancel={() => setForm(null)}
        />
      )}
      {editable && !form && (
        <Button variant="link" onClick={() => open(null)}>
          Add image to this step
        </Button>
      )}
      <Dialog
        open={removing !== null}
        title="Remove this picture?"
        description={
          removing ? `“${removing.caption}” will be removed from this step. This can't be undone; upload it again to bring it back.` : undefined
        }
        onClose={() => setRemoving(null)}
        actions={
          <>
            <Button variant="secondary" onClick={() => setRemoving(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmRemove} aria-busy={remove.isPending || undefined}>
              {remove.isPending ? "Removing…" : "Remove picture"}
            </Button>
          </>
        }
      >
        {remove.isError && (
          <p className="panel-danger" role="alert">
            {messageOf(remove.error)}
          </p>
        )}
      </Dialog>
    </PanelSection>
  );
}
