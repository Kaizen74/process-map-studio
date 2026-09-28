import { request } from "./request";
import type { QualityCard, VersionDetail, VersionSummary } from "./types";
import type { AlignmentRow } from "../lib/matrix";

const enc = encodeURIComponent;

// API_CONTRACT.md → Draft (quality card) and Versions, publish and exports (phase P7).
export const getQualityCard = (versionId: string) => request<QualityCard>(`/versions/${enc(versionId)}/quality-card`);

export const getVersion = (versionId: string) => request<VersionDetail>(`/versions/${enc(versionId)}`);

export const listVersions = (engagementId: string) =>
  request<VersionSummary[]>(`/engagements/${enc(engagementId)}/versions`);

export const publishVersion = (versionId: string) =>
  request<VersionDetail>(`/versions/${enc(versionId)}/publish`, { method: "POST" });

export const reopenVersion = (versionId: string) =>
  request<VersionDetail>(`/versions/${enc(versionId)}/reopen`, { method: "POST" });

// API_CONTRACT.md → Views (phase P9).
export const getAlignmentMatrix = (versionId: string) =>
  request<AlignmentRow[]>(`/versions/${enc(versionId)}/alignment-matrix`);
