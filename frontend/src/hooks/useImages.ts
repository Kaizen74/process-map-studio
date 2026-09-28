import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { changeImage, listStepImages, listVersionImages, removeImage, uploadImage, type ImageChange } from "../api/images";
import type { ImageDetails } from "../lib/images";
import { refreshReview } from "./useReview";

export function useStepImages(elementId: string | null) {
  return useQuery({
    queryKey: ["elements", elementId ?? "", "images"],
    queryFn: () => listStepImages(elementId ?? ""),
    enabled: Boolean(elementId),
  });
}

export function useVersionImages(versionId: string | null) {
  return useQuery({
    queryKey: ["versions", versionId ?? "", "images"],
    queryFn: () => listVersionImages(versionId ?? ""),
    enabled: Boolean(versionId),
  });
}

/** A picture changed: the step (its pictures and count), the version's pictures (marker, strip),
 * and everything that shows review state (Q6, audit). */
function refreshImages(client: QueryClient, elementId: string, versionId: string, engagementId: string) {
  void client.invalidateQueries({ queryKey: ["elements", elementId] });
  void client.invalidateQueries({ queryKey: ["versions", versionId, "images"] });
  refreshReview(client, versionId, engagementId);
}

export function useImageChanges(elementId: string, versionId: string, engagementId: string) {
  const client = useQueryClient();
  const onSuccess = () => refreshImages(client, elementId, versionId, engagementId);
  const upload = useMutation({ mutationFn: (details: ImageDetails) => uploadImage(elementId, details), onSuccess });
  const change = useMutation({
    mutationFn: ({ imageId, body }: { imageId: string; body: ImageChange }) => changeImage(imageId, body),
    onSuccess,
  });
  const remove = useMutation({ mutationFn: (imageId: string) => removeImage(imageId), onSuccess });
  return { upload, change, remove };
}
