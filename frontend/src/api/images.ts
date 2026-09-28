import { request } from "./request";
import type { ImageDetails, ImageType, StepImage } from "../lib/images";

const enc = encodeURIComponent;

// API_CONTRACT.md → Images (phase P8).
export const listStepImages = (elementId: string) => request<StepImage[]>(`/elements/${enc(elementId)}/images`);

export const listVersionImages = (versionId: string) => request<StepImage[]>(`/versions/${enc(versionId)}/images`);

export function uploadImage(elementId: string, details: ImageDetails) {
  const form = new FormData();
  if (details.file) form.append("file", details.file);
  form.append("caption", details.caption.trim());
  form.append("image_type", details.imageType);
  form.append("redaction_confirmed", details.confirmed ? "true" : "false");
  return request<StepImage>(`/elements/${enc(elementId)}/images`, { method: "POST", body: form });
}

export interface ImageChange {
  status?: "kept" | "discarded";
  caption?: string;
  image_type?: ImageType;
  redaction_confirmed?: boolean;
}

export const changeImage = (imageId: string, change: ImageChange) =>
  request<StepImage>(`/images/${enc(imageId)}`, { method: "PATCH", body: change });

export const removeImage = (imageId: string) => request<null>(`/images/${enc(imageId)}`, { method: "DELETE" });
