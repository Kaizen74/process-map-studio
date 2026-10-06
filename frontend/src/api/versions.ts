import { request } from "./request";
import type { QualityCard, VersionDetail, VersionSummary } from "./types";
import type { AlignmentRow } from "../lib/matrix";
import type { CauseEntry, Registers, Theme, ThemeStatus, ValidationResult } from "../lib/registers";

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

export const getRegisters = (versionId: string) => request<Registers>(`/versions/${enc(versionId)}/registers`);

export const listCauses = (engagementId: string) =>
  request<CauseEntry[]>(`/engagements/${enc(engagementId)}/cause-library`);

export const validateCause = (causeId: string, result: ValidationResult) =>
  request<CauseEntry>(`/cause-library/${enc(causeId)}`, { method: "PATCH", body: { validation_result: result } });

// API_CONTRACT.md → Emerging themes (C7b).
export const listThemes = (engagementId: string) => request<Theme[]>(`/engagements/${enc(engagementId)}/themes`);

export const decideTheme = (themeId: string, body: { status: ThemeStatus; theme?: string; note?: string }) =>
  request<Theme>(`/themes/${enc(themeId)}`, { method: "PATCH", body });

