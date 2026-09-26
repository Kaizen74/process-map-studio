import { request } from "./request";
import type { SegmentPage, Source, SourcePatch, SourceUpload } from "./types";

const enc = encodeURIComponent;

export const listSources = (engagementId: string) => request<Source[]>(`/engagements/${enc(engagementId)}/sources`);

export const getSource = (sourceId: string) => request<Source>(`/sources/${enc(sourceId)}`);

export function uploadSource(engagementId: string, upload: SourceUpload) {
  const form = new FormData();
  form.append("file", upload.file, upload.file.name);
  if (upload.kind) form.append("kind", upload.kind);
  return request<Source>(`/engagements/${enc(engagementId)}/sources`, { method: "POST", body: form });
}

export const updateSource = (sourceId: string, patch: SourcePatch) =>
  request<Source>(`/sources/${enc(sourceId)}`, { method: "PATCH", body: patch });

export const deleteSource = (sourceId: string) => request<null>(`/sources/${enc(sourceId)}`, { method: "DELETE" });

export const listSegments = (sourceId: string, page: number, pageSize = 200) =>
  request<SegmentPage>(`/sources/${enc(sourceId)}/segments?page=${page}&page_size=${pageSize}`);
