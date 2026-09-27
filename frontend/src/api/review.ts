import { request } from "./request";
import type { ElementDetail, Layout, SegmentPage } from "./types";

const enc = encodeURIComponent;

// API_CONTRACT.md → Draft (layout) and Review (phase P5). The graph itself: api/draft.ts.
export const getLayout = (versionId: string) => request<Layout>(`/versions/${enc(versionId)}/layout`);

export const getElement = (elementId: string) => request<ElementDetail>(`/elements/${enc(elementId)}`);

/** The page of a source that holds one passage (the source viewer opened from evidence). */
export const listSegmentsAround = (sourceId: string, segmentId: string, pageSize = 200) =>
  request<SegmentPage>(`/sources/${enc(sourceId)}/segments?around=${enc(segmentId)}&page_size=${pageSize}`);
