import type { CoverageReport } from "../lib/coverage";
import type {
  GuideEdit,
  GuideStarted,
  GuideSummary,
  GuideView,
  OwnerProbe,
  Profile,
  ProfileInput,
} from "../lib/interview";
import { request } from "./request";

export type { GuideEdit, GuideStarted, GuideSummary, GuideView, OwnerProbe, Profile, ProfileInput };

// API_CONTRACT.md → Interviewee profiles (phase P4c, C5a).
const enc = encodeURIComponent;

export const listProfiles = (engagementId: string) =>
  request<Profile[]>(`/engagements/${enc(engagementId)}/profiles`);

export const addProfile = (engagementId: string, body: ProfileInput) =>
  request<Profile>(`/engagements/${enc(engagementId)}/profiles`, { method: "POST", body });

export const editProfile = (profileId: string, patch: Partial<ProfileInput>) =>
  request<Profile>(`/profiles/${enc(profileId)}`, { method: "PATCH", body: patch });

// API_CONTRACT.md → Tailored interview guides (G1, G2): the full guide is only downloaded.
export const listGuides = (engagementId: string) =>
  request<GuideSummary[]>(`/engagements/${enc(engagementId)}/interview-guides`);

export const makeGuide = (engagementId: string, profileId: string) =>
  request<GuideStarted>(`/engagements/${enc(engagementId)}/interview-guide`, {
    method: "POST",
    body: { profile_id: profileId },
  });

export const getGuide = (engagementId: string, profileId: string) =>
  request<GuideView>(`/engagements/${enc(engagementId)}/interview-guide?profile_id=${enc(profileId)}`);

export const editGuide = (engagementId: string, profileId: string, body: GuideEdit) =>
  request<GuideView>(`/engagements/${enc(engagementId)}/interview-guide?profile_id=${enc(profileId)}`, {
    method: "PATCH",
    body,
  });

// API_CONTRACT.md → GET /versions/{vid}/coverage (C4; shown on the Coverage tab, C5d).
export const getCoverage = (versionId: string) => request<CoverageReport>(`/versions/${enc(versionId)}/coverage`);


// DECISIONS 113: Eric's own suggested probes (one per line when pasted).
export const listProbes = (engagementId: string) => request<OwnerProbe[]>(`/engagements/${enc(engagementId)}/probes`);

export const addProbes = (engagementId: string, body: { text: string; about?: string }) =>
  request<OwnerProbe[]>(`/engagements/${enc(engagementId)}/probes`, { method: "POST", body });

export const updateProbe = (probeId: string, body: { text?: string; about?: string }) =>
  request<OwnerProbe>(`/probes/${enc(probeId)}`, { method: "PATCH", body });

export const deleteProbe = (probeId: string) => request<null>(`/probes/${enc(probeId)}`, { method: "DELETE" });
