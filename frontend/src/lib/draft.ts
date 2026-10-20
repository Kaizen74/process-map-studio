// Draft screen display rules (PRD §5.4 Draft): stage labels and shapes, elapsed times and token
// counts. Pure functions; the stages and their times come from the backend job.
import type { DraftEstimate, JobStage, Readiness, StageStatus } from "../api/types";
import { plural } from "./format";

export interface StageLook {
  label: string;
  /** Shape drawn next to the stage: every status has its own shape as well as its text. */
  shape: "filled-circle" | "half-circle" | "dashed-ring" | "ring-cross" | "outlined-square" | "dash";
  tone: "good" | "neutral" | "danger";
}

export const STAGE_LOOK: Readonly<Record<StageStatus, StageLook>> = {
  done: { label: "Done", shape: "filled-circle", tone: "good" },
  running: { label: "Running", shape: "half-circle", tone: "good" },
  waiting: { label: "Waiting", shape: "dashed-ring", tone: "neutral" },
  failed: { label: "Failed", shape: "ring-cross", tone: "danger" },
  skipped: { label: "Switched off in Settings", shape: "dash", tone: "neutral" },
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
  key: "key" | "source" | "transcript" | "document" | "speakers";
  label: string;
  done: boolean;
  /** False for what makes the map stronger but doesn't stop the draft (the other kind of source). */
  required: boolean;
  /** Where to fix it. */
  to: "settings" | "sources";
  action: string;
}

/**
 * The Draft readiness checklist (PRD §5.4), from the readiness endpoint. A process document is
 * recommended, not required: a draft from interviews alone is allowed at Limited signal (P12).
 */
export function draftChecklist(readiness: Readiness): ChecklistItem[] {
  // A draft needs a source that describes the steps: an interview or, since 2026-10-20 (Eric), a
  // process document alone. The other kind is recommended. Speakers count once a transcript is read.
  const items: ChecklistItem[] = [
    {
      key: "key",
      required: true,
      label: "Claude API key saved",
      done: readiness.key_set,
      to: "settings",
      action: "Add it in Settings",
    },
    {
      key: "source",
      required: true,
      label: "An interview transcript or a process document (an SOP or manual) read",
      done: readiness.transcripts_ready || readiness.documents_ready,
      to: "sources",
      action: "Go to Sources",
    },
    {
      key: "transcript",
      required: false,
      label: "An interview transcript read: recommended, it shows how the work is actually done",
      done: readiness.transcripts_ready,
      to: "sources",
      action: "Go to Sources",
    },
    {
      key: "document",
      required: false,
      label: "A process document read (an SOP or manual): recommended for a stronger map",
      done: readiness.documents_ready,
      to: "sources",
      action: "Go to Sources",
    },
  ];
  if (readiness.transcripts_ready) {
    items.push({
      key: "speakers",
      required: true,
      label: "Every speaker mapped to a role",
      done: readiness.speakers_unmapped === 0,
      to: "sources",
      action: "Map speakers in Sources",
    });
  }
  return items;
}

/** "3 of 3 ready.": only the required items count; the other kind of source is recommended. */
export function checklistSummary(items: ChecklistItem[]): string {
  const required = items.filter((i) => i.required);
  return `${required.filter((i) => i.done).length} of ${required.length} ready.`;
}

const STAGE_NAMES: Readonly<Record<string, string>> = {
  S0_ocr_page: "Reading a scanned page",
  S1_extract_interview: "Extracting steps (interview)",
  S1_extract_document: "Extracting steps (document)",
  S1_extract_jd: "Extracting roles (job description)",
  S2_canonicalise: "Grouping claims into steps",
  S3_calibrate: "Comparing a source with the steps",
  S3b_verify: "Independent verification of a step",
  S4_assemble: "Building the map",
  S5_questions: "Writing validation questions",
  R_repair: "Fixing an answer's format",
  // Gap analysis (P10).
  GA_internal: "Comparing documents with practice",
  GA_verify: "Independent check of a gap finding",
  GB_research: "Web research (searches your approved brief)",
  GB_structure: "Sorting the research into findings",
  GB_verify: "Independent check of a research finding",
  GB_test: "Web search test",
};

/** A stage ID from the AI usage log in plain words; unknown IDs are shown as they are. */
export function aiStageName(stageId: string): string {
  return STAGE_NAMES[stageId] ?? stageId;
}

export const AI_CALL_STATUS: Readonly<Record<string, string>> = {
  ok: "OK",
  error: "Failed",
  mock: "Test answer",
  invalid: "Wrong format",
  repaired: "Repaired",
  truncated: "Cut off",
  refused: "Declined",
};

/** "14.2 s", "850 ms". */
export function durationLabel(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** "US$0.67", "US$12.40"; "less than US$0.01" for a cost that rounds to nothing. */
export function usd(amount: number): string {
  const cents = Math.round(amount * 100);
  if (cents < 1) return "less than US$0.01";
  return `US$${groupDigits(Math.floor(cents / 100))}.${String(cents % 100).padStart(2, "0")}`;
}

const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "19 Oct 2026" from a plain date "2026-10-19", read as written (no time zone shift). */
function plainDate(day: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  const month = m ? MONTH[Number(m[2]) - 1] : undefined;
  return m && month ? `${Number(m[3])} ${month} ${m[1]}` : day;
}

/**
 * The cost line under Create draft map (2026-10-19, deep review item 5): the estimate, how it was
 * worked out and the day the prices were checked; a second sentence when it is above the limit.
 */
export function estimateLines(e: DraftEstimate): { cost: string; limit: string | null } {
  if (e.cost_usd === null) {
    return {
      cost: `No cost estimate: the price of ${e.model} isn't in the app's price list.`,
      limit: e.limit_usd === null ? null : "Your spending limit can't be checked without a price, so it doesn't stop this draft.",
    };
  }
  const basis =
    e.basis === "measured"
      ? `based on your last ${plural(e.drafts_measured, "real draft")}`
      : "a rough rule until your first real draft";
  return {
    cost: `Estimated cost: about ${usd(e.cost_usd)} for ${plural(e.sources, "source")} (${basis}; prices checked ${plainDate(e.prices_checked_on)}).`,
    limit:
      e.over_limit && e.limit_usd !== null
        ? `That is above your limit of ${usd(e.limit_usd)}, so the draft won't start. Raise the limit in Settings, or draft from fewer sources.`
        : null,
  };
}
