import { request } from "./request";
import type { DraftState, Job, RejectedClaims } from "./types";

const enc = encodeURIComponent;

// API_CONTRACT.md → Draft (phase P3).
export const startDraft = (engagementId: string) =>
  request<{ job_id: string }>(`/engagements/${enc(engagementId)}/draft`, { method: "POST" });

export const getDraft = (engagementId: string) =>
  request<DraftState>(`/engagements/${enc(engagementId)}/draft`);

export const getJob = (jobId: string) => request<Job>(`/jobs/${enc(jobId)}`);

export const getRejectedClaims = (versionId: string) =>
  request<RejectedClaims>(`/versions/${enc(versionId)}/rejected-claims`);
