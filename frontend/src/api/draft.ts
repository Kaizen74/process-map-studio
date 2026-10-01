import { request } from "./request";
import type { DraftState, Graph, Job, LintReport, RefreshCheck, RejectedClaims } from "./types";
import type { AsView } from "../lib/views";

const enc = encodeURIComponent;

// API_CONTRACT.md → Draft (phase P3).
export const startDraft = (engagementId: string) =>
  request<{ job_id: string }>(`/engagements/${enc(engagementId)}/draft`, { method: "POST" });

export const getDraft = (engagementId: string) =>
  request<DraftState>(`/engagements/${enc(engagementId)}/draft`);

export const getJob = (jobId: string) => request<Job>(`/jobs/${enc(jobId)}`);

export const getRejectedClaims = (versionId: string) =>
  request<RejectedClaims>(`/versions/${enc(versionId)}/rejected-claims`);

/** Every step and line; with a view (§3.12.11) only its steps and lines, and its cycle time. */
export const getGraph = (versionId: string, view?: AsView) =>
  request<Graph>(`/versions/${enc(versionId)}/graph${view ? `?view=${view}` : ""}`);

export const getLint = (versionId: string) => request<LintReport>(`/versions/${enc(versionId)}/lint`);

/** Refresh draft from sources (phase P6): reviewed steps stay exactly as they are. */
export const startRefresh = (versionId: string) =>
  request<{ job_id: string }>(`/versions/${enc(versionId)}/refresh`, { method: "POST" });

/** What a refresh would use differently from the run that made this draft (no AI call). */
export const getRefreshCheck = (versionId: string) =>
  request<RefreshCheck>(`/versions/${enc(versionId)}/refresh-check`);
