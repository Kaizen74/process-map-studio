import { request } from "./request";
import type { QualityCard, VersionDetail, VersionSummary } from "./types";

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

export type ExportFormat = "md" | "json" | "csv" | "html";

/** The download address of an export (a plain link: the browser saves the file). */
export const exportUrl = (versionId: string, format: ExportFormat) =>
  `/api/versions/${enc(versionId)}/export/${format}`;
