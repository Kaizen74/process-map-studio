import { request } from "./request";
import type { Segment, SegmentPage, Source, SourcePatch, SourceUpload, Speaker, SpeakerMapping } from "./types";

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

export const listSegments = (sourceId: string, page: number, pageSize = 200, raw = false) =>
  request<SegmentPage>(
    `/sources/${enc(sourceId)}/segments?page=${page}&page_size=${pageSize}${raw ? "&raw=1" : ""}`,
  );

// Owner-only places (PRD §3.8 G10): speaker labels and raw text may contain names.
export const getSpeakers = (sourceId: string) => request<Speaker[]>(`/sources/${enc(sourceId)}/speakers`);

export const mapSpeakers = (sourceId: string, mapping: SpeakerMapping) =>
  request<Speaker[]>(`/sources/${enc(sourceId)}/speakers`, { method: "PUT", body: mapping });

export const correctSegment = (segmentId: string, text: string) =>
  request<Segment>(`/segments/${enc(segmentId)}`, { method: "PATCH", body: { text } });
