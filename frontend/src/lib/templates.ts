// Standard interview templates (PRD v1.10 Appendix F.9): the same questions, question IDs and minute
// plan for every interviewer, before any engagement exists. Downloads are plain links to
// `GET /api/templates/interview`; the browser saves the file the server names.

export type InterviewType = "landscape" | "practice" | "follow_up";
export type TemplateFormat = "docx" | "md";

export interface TemplatePlanRow {
  label: string;
  minutes: number;
}

/** GET /api/templates/interview/plans: what the cards show for each template. */
export interface TemplateSummary {
  type: InterviewType;
  title: string;
  minutes: number;
  who: string;
  purpose: string;
  plan: TemplatePlanRow[];
  question_count: number;
  bank_version: string;
}

export const FORMATS: readonly { format: TemplateFormat; label: string }[] = [
  { format: "docx", label: "Word" },
  { format: "md", label: "Markdown" },
];

/** How to use the question IDs in an interview (the templates' footer says the same). */
export const QUESTION_ID_TIP =
  "Say or note the question ID (for example [M2.2]) when you ask it: it helps the app link each answer to its question. Use roles, not names.";

export function templateUrl(type: InterviewType, format: TemplateFormat): string {
  return `/api/templates/interview?type=${type}&format=${format}`;
}
