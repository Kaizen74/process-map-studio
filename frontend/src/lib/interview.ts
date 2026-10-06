// Interviewee profiles (API_CONTRACT.md → Interviewee profiles; C5a): shared by the API layer and
// the components (components never import src/api).
export type InterviewType = "landscape" | "practice" | "follow_up";

export interface Profile {
  id: string;
  engagement_id: string;
  role_id: string | null;
  role_name: string;
  stakeholder_group: string;
  interview_type: InterviewType;
  referred_by_role: string;
  previous_profile_id: string | null;
  created_at: string;
}

export interface ProfileInput {
  role_id: string | null;
  stakeholder_group: string;
  interview_type: InterviewType;
  referred_by_role: string;
  previous_profile_id: string | null;
}


export const INTERVIEW_TYPE_LABELS: Readonly<Record<InterviewType, string>> = {
  landscape: "Landscape",
  practice: "Practice",
  follow_up: "Follow-up",
};

/** "Ramp agent · Ramp" or whichever of the two the profile has. */
export function profileName(profile: Pick<Profile, "role_name" | "stakeholder_group">): string {
  return [profile.role_name, profile.stakeholder_group].filter(Boolean).join(" · ");
}

/** POST /engagements/{id}/interview-guide: the job making a new version (C5b). */
export interface GuideStarted {
  job_id: string;
  profile_id: string;
}

/** GET /engagements/{id}/interview-guides: an interviewee's latest tailored guide (G2). */
export interface GuideSummary {
  id: string;
  profile_id: string | null;
  interview_type: InterviewType;
  version: number;
  created_at: string;
}

/** The latest guide of one interviewee as a Word or Markdown file (the server names the file). */
export function guideUrl(engagementId: string, profileId: string, format: "docx" | "md"): string {
  const enc = encodeURIComponent;
  return `/api/engagements/${enc(engagementId)}/interview-guide/export?profile_id=${enc(profileId)}&format=${format}`;
}
