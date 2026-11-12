import { request } from "./request";
import type { HandoffPreview, TestingItem, TestingPatch } from "./types";

const enc = encodeURIComponent;

/** Read a Capability Compass hand-off file and say what it would create (applies nothing). */
export const previewHandoff = (handoff: unknown) =>
  request<HandoffPreview>("/compass/preview", { method: "POST", body: { handoff } });

export const listTesting = (engagementId: string) =>
  request<TestingItem[]>(`/engagements/${enc(engagementId)}/testing`);

export const addTesting = (engagementId: string, item: { ref: string; text: string; refuted_by: string }) =>
  request<TestingItem>(`/engagements/${enc(engagementId)}/testing`, { method: "POST", body: item });

export const updateTesting = (itemId: string, patch: TestingPatch) =>
  request<TestingItem>(`/testing/${enc(itemId)}`, { method: "PATCH", body: patch });

export const deleteTesting = (itemId: string) => request<null>(`/testing/${enc(itemId)}`, { method: "DELETE" });
