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

// --- A guide's content and Eric's edits (API_CONTRACT.md → Tailored interview guides; C5c) ---

/** One question row: ID · question · probes · minutes, and what it is for (not printed). */
export interface GuideRow {
  id: string;
  lead_in: string;
  wording: string;
  note: string;
  probes: string[];
  minutes: string;
  signifier: boolean;
  movement: string;
  targets: string[];
  priority: string;
  /** SOP-derived probes parked in M6 (F.8 rule 5). */
  held_back: string[];
}

export interface GuideTable {
  label: string;
  minutes: number;
  note: string;
  rows: GuideRow[];
}

export interface GuideDocument {
  kind: InterviewType;
  title: string;
  minutes: number;
  tables: GuideTable[];
  generation_note: string;
}

export interface GuideView {
  id: string;
  engagement_id: string;
  profile_id: string | null;
  interview_type: InterviewType;
  version: number;
  edited: boolean;
  created_at: string;
  document: GuideDocument;
  /** Prompts from the Capability Compass hand-off, offered beside the guide; never evidence. */
  suggested_probes?: string[];
}

export interface RowEdit {
  id: string;
  wording: string;
  probes: string[];
  held_back: string[];
}

/** PATCH …/interview-guide: every section and row, in order. */
export interface GuideEdit {
  tables: { label: string; rows: RowEdit[] }[];
}

export function toEdit(document: GuideDocument): GuideEdit {
  return {
    tables: document.tables.map((t) => ({
      label: t.label,
      rows: t.rows.map((r) => ({ id: r.id, wording: r.wording, probes: [...r.probes], held_back: [...r.held_back] })),
    })),
  };
}

/** "tables[2].rows[3].probes[0]" → [2, 3, "probes"]: where the server's refusal belongs. */
export function editFieldOf(field: string | undefined): [number, number, string] | null {
  const match = /^tables\[(\d+)\]\.rows\[(\d+)\]\.(\w+)/.exec(field ?? "");
  return match ? [Number(match[1]), Number(match[2]), match[3] ?? ""] : null;
}

/** Probes edited one per line. */
export const linesOf = (text: string): string[] => text.split("\n");

