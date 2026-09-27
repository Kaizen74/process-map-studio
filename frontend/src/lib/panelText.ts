// Plain words for the codes the detail panel shows (PRD §5.1: a code is always paired with, or
// replaced by, a sentence). Pure data.

/** "single_point_knowledge" → "Single point knowledge". */
export function words(code: string): string {
  const text = code.replaceAll("_", " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

export const SOURCE_KINDS: Readonly<Record<string, string>> = {
  interview_transcript: "Interview",
  sop: "SOP",
  manual: "Manual",
  job_description: "Job description",
  executed_artefact: "Executed artefact",
  other: "Document",
};

export const MECHANISMS: Readonly<Record<string, string>> = {
  rule_based: "Rule-based",
  judgment: "Judgment",
  none: "Not stated",
};

export const AI_BASES: Readonly<Record<string, string>> = {
  rule_based_automate_candidate: "Rule-based: an automation candidate",
  judgment_support_only: "Judgment: support the person, never automate",
};

/** "+0.60", "−0.20" (a real minus sign), two decimals as PRD §5.3 asks. */
export function signed(delta: number): string {
  const text = Math.abs(delta).toFixed(2);
  return delta < 0 ? `−${text}` : `+${text}`;
}
