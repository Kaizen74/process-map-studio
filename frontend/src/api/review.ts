import { request } from "./request";
import type { ElementDetail, Layout, SegmentPage } from "./types";
import type { StepPatch } from "../lib/stepForm";

const enc = encodeURIComponent;

// API_CONTRACT.md → Draft (layout) and Review (phase P5). The graph itself: api/draft.ts.
export const getLayout = (versionId: string) => request<Layout>(`/versions/${enc(versionId)}/layout`);

export const getElement = (elementId: string) => request<ElementDetail>(`/elements/${enc(elementId)}`);

/** The page of a source that holds one passage (the source viewer opened from evidence). */
export const listSegmentsAround = (sourceId: string, segmentId: string, pageSize = 200) =>
  request<SegmentPage>(`/sources/${enc(sourceId)}/segments?around=${enc(segmentId)}&page_size=${pageSize}`);

// Review actions (phase P6).
export type ReviewAction = "confirm" | "reject" | "restore";

export const reviewElement = (elementId: string, action: ReviewAction) =>
  request<ElementDetail>(`/elements/${enc(elementId)}/${action}`, { method: "POST" });

/** Edit a step: only the fields sent change (PATCH /elements/{eid}). */
export const updateElement = (elementId: string, patch: Partial<StepPatch>) =>
  request<ElementDetail>(`/elements/${enc(elementId)}`, { method: "PATCH", body: patch });
