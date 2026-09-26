// Draft screen display rules (PRD §5.4 Draft): stage labels and shapes, elapsed times and token
// counts. Pure functions; the stages and their times come from the backend job.
import type { JobStage, Readiness, StageStatus } from "../api/types";

export interface StageLook {
  label: string;
  /** Shape drawn next to the stage: every status has its own shape as well as its text. */
  shape: "filled-circle" | "half-circle" | "dashed-ring" | "ring-cross" | "outlined-square";
  tone: "good" | "neutral" | "danger";
}

export const STAGE_LOOK: Readonly<Record<StageStatus, StageLook>> = {
  done: { label: "Done", shape: "filled-circle", tone: "good" },
  running: { label: "Running", shape: "half-circle", tone: "good" },
  waiting: { label: "Waiting", shape: "dashed-ring", tone: "neutral" },
  failed: { label: "Failed", shape: "ring-cross", tone: "danger" },
  later: { label: "Later build phase", shape: "outlined-square", tone: "neutral" },
};

const pad = (n: number) => String(n).padStart(2, "0");

/** "45 s", "2 min 05 s", "1 h 02 min". */
export function elapsedLabel(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ${pad(seconds % 60)} s`;
  return `${Math.floor(minutes / 60)} h ${pad(minutes % 60)} min`;
}

/** How long a stage ran (or has been running, measured to `now`); null if it hasn't started. */
export function stageElapsedMs(stage: JobStage, now: number): number | null {
  if (!stage.started_at) return null;
  const start = Date.parse(stage.started_at);
  const end = stage.finished_at ? Date.parse(stage.finished_at) : now;
  return Number.isNaN(start) || Number.isNaN(end) ? null : Math.max(0, end - start);
}

/** "15,400": thousands separated the same way on every computer. */
export function groupDigits(n: number): string {
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export interface ChecklistItem {
  key: "key" | "transcript" | "document" | "speakers";
  label: string;
  done: boolean;
  /** Where to fix it. */
  to: "settings" | "sources";
  action: string;
}

/** The Draft readiness checklist (PRD §5.4), from the readiness endpoint. */
export function draftChecklist(readiness: Readiness): ChecklistItem[] {
  return [
    {
      key: "key",
      label: "Claude API key saved",
      done: readiness.key_set,
      to: "settings",
      action: "Add it in Settings",
    },
    {
      key: "transcript",
      label: "At least one interview transcript read",
      done: readiness.transcripts_ready,
      to: "sources",
      action: "Go to Sources",
    },
    {
      key: "document",
      label: "At least one process document read (an SOP or manual)",
      done: readiness.documents_ready,
      to: "sources",
      action: "Go to Sources",
    },
    {
      key: "speakers",
      label: "Every speaker mapped to a role",
      done: readiness.transcripts_ready && readiness.speakers_unmapped === 0,
      to: "sources",
      action: "Map speakers in Sources",
    },
  ];
}

const STAGE_NAMES: Readonly<Record<string, string>> = {
  S0_ocr_page: "Reading a scanned page",
  S1_extract_interview: "Extracting steps (interview)",
  S1_extract_document: "Extracting steps (document)",
  S1_extract_jd: "Extracting roles (job description)",
  R_repair: "Fixing an answer's format",
};

/** A stage ID from the AI usage log in plain words; unknown IDs are shown as they are. */
export function aiStageName(stageId: string): string {
  return STAGE_NAMES[stageId] ?? stageId;
}

export const AI_CALL_STATUS: Readonly<Record<string, string>> = {
  ok: "OK",
  error: "Failed",
  mock: "Test answer",
};

/** "14.2 s", "850 ms". */
export function durationLabel(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}
