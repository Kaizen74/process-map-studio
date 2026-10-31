import { request } from "./request";
import type {
  DraftEstimate,
  DraftState,
  Graph,
  Job,
  LintReport,
  OutsideFlowClaims,
  RefreshCheck,
  RejectedClaims,
} from "./types";
import type { AsView } from "../lib/views";

const enc = encodeURIComponent;

// API_CONTRACT.md → Draft (phase P3).
export const startDraft = (engagementId: string) =>
  request<{ job_id: string }>(`/engagements/${enc(engagementId)}/draft`, { method: "POST" });

export const getDraft = (engagementId: string) =>
  request<DraftState>(`/engagements/${enc(engagementId)}/draft`);

/** What drafting now would probably cost (no AI call). */
export const getDraftEstimate = (engagementId: string) =>
  request<DraftEstimate>(`/engagements/${enc(engagementId)}/draft/estimate`);

export const getJob = (jobId: string) => request<Job>(`/jobs/${enc(jobId)}`);

export const getRejectedClaims = (versionId: string) =>
  request<RejectedClaims>(`/versions/${enc(versionId)}/rejected-claims`);

/** Checked claims about another flow, kept off this map (DECISIONS 81). */
export const getOutsideFlow = (versionId: string) =>
  request<OutsideFlowClaims>(`/versions/${enc(versionId)}/outside-flow`);

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
