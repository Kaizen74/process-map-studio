import type { Profile, ProfileInput } from "../lib/interview";
import { request } from "./request";

export type { Profile, ProfileInput };

// API_CONTRACT.md → Interviewee profiles (phase P4c, C5a).
const enc = encodeURIComponent;

export const listProfiles = (engagementId: string) =>
  request<Profile[]>(`/engagements/${enc(engagementId)}/profiles`);

export const addProfile = (engagementId: string, body: ProfileInput) =>
  request<Profile>(`/engagements/${enc(engagementId)}/profiles`, { method: "POST", body });

export const editProfile = (profileId: string, patch: Partial<ProfileInput>) =>
  request<Profile>(`/profiles/${enc(profileId)}`, { method: "PATCH", body: patch });
