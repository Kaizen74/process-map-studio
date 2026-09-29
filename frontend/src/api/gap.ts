import { request } from "./request";
import type {
  Brief,
  FindingDecision,
  GapAnalysis,
  GapBriefView,
  GapFinding,
  GapReport,
  GapStarted,
} from "../lib/gap";

const enc = encodeURIComponent;

// API_CONTRACT.md → Gap analysis (phase P10).
export const listAnalyses = (versionId: string) =>
  request<GapAnalysis[]>(`/versions/${enc(versionId)}/gap-analyses`);

export const getReport = (analysisId: string) => request<GapReport>(`/gap-analyses/${enc(analysisId)}`);

export const startInternal = (versionId: string) =>
  request<GapStarted>(`/versions/${enc(versionId)}/gap-analyses/internal`, { method: "POST" });

export const startExternal = (versionId: string) =>
  request<GapBriefView>(`/versions/${enc(versionId)}/gap-analyses/external`, { method: "POST" });

export const updateBrief = (analysisId: string, brief: Brief, confirmed: boolean) =>
  request<GapBriefView>(`/gap-analyses/${enc(analysisId)}/brief`, {
    method: "PATCH",
    body: { brief, confirmed },
  });

export const runResearch = (analysisId: string) =>
  request<GapStarted>(`/gap-analyses/${enc(analysisId)}/run`, { method: "POST" });

export const decideFinding = (findingId: string, decision: FindingDecision) =>
  request<GapFinding>(`/gap-findings/${enc(findingId)}`, { method: "PATCH", body: decision });

export const finaliseReport = (analysisId: string) =>
  request<GapReport>(`/gap-analyses/${enc(analysisId)}/finalise`, { method: "POST" });
