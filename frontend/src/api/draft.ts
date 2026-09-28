import { request } from "./request";
import type { DraftState, Graph, Job, LintReport, RejectedClaims } from "./types";

const enc = encodeURIComponent;

// API_CONTRACT.md → Draft (phase P3).
export const startDraft = (engagementId: string) =>
  request<{ job_id: string }>(`/engagements/${enc(engagementId)}/draft`, { method: "POST" });

export const getDraft = (engagementId: string) =>
  request<DraftState>(`/engagements/${enc(engagementId)}/draft`);

export const getJob = (jobId: string) => request<Job>(`/jobs/${enc(jobId)}`);

export const getRejectedClaims = (versionId: string) =>
  request<RejectedClaims>(`/versions/${enc(versionId)}/rejected-claims`);

export const getGraph = (versionId: string) => request<Graph>(`/versions/${enc(versionId)}/graph`);

export const getLint = (versionId: string) => request<LintReport>(`/versions/${enc(versionId)}/lint`);

/** Refresh draft from sources (phase P6): reviewed steps stay exactly as they are. */
export const startRefresh = (versionId: string) =>
  request<{ job_id: string }>(`/versions/${enc(versionId)}/refresh`, { method: "POST" });
