// Source kinds, accepted formats and status wording (API_CONTRACT.md → Sources; PRD B.1, §5.4).
import type { Source } from "../api/types";

export const KIND_OPTIONS = [
  { value: "interview_transcript", label: "Interview transcript" },
  { value: "sop", label: "SOP" },
  { value: "manual", label: "Manual" },
  { value: "job_description", label: "Job description" },
  { value: "executed_artefact", label: "Executed artefact" },
  { value: "working_spreadsheet", label: "Working spreadsheet" },
  { value: "email_thread", label: "Email thread" },
  { value: "other", label: "Other document" },
] as const;

export function kindLabel(kind: string): string {
  return KIND_OPTIONS.find((k) => k.value === kind)?.label ?? kind;
}

export const ACCEPTED_FORMATS = [".docx", ".pdf", ".txt", ".vtt", ".srt", ".xlsx", ".csv", ".eml"] as const;
export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
export const BAD_FORMAT = "Process Map Studio reads .docx, .pdf, .txt, .vtt, .srt, .xlsx, .csv and .eml files.";
export const TOO_BIG = "That file is larger than 50 MB. Split it or save a smaller copy, then upload again.";

/** null when the file can be uploaded, otherwise why not (same wording as the server). */
export function uploadProblem(file: { name: string; size: number }): string | null {
  const name = file.name.toLowerCase();
  if (!ACCEPTED_FORMATS.some((ext) => name.endsWith(ext))) return BAD_FORMAT;
  if (file.size > MAX_UPLOAD_BYTES) return TOO_BIG;
  return null;
}

export interface SourceStatus {
  label: string;
  tone: "neutral" | "good" | "danger";
  dashed: boolean;
}

/** Status chip wording (PRD §5.4 Sources: Reading… · Ready · Failed + reason). "pending" means its
 * background reading job hasn't finished yet. */
export function sourceStatus(source: Pick<Source, "text_status">): SourceStatus {
  switch (source.text_status) {
    case "ready":
      return { label: "Ready", tone: "good", dashed: false };
    case "failed":
      return { label: "Failed", tone: "danger", dashed: false };
    default:
      return { label: "Reading…", tone: "neutral", dashed: true };
  }
}

/** Coverage (PRD §3.8 G11) as shown: "50%", "33.3%"; null when not measured yet. */
export function coverageText(pct: number | null | undefined): string | null {
  if (pct === null || pct === undefined) return null;
  return `${Number.isInteger(pct) ? pct : pct.toFixed(1)}%`;
}

export const NOT_MEASURED = "Measured after a draft that uses this file";
