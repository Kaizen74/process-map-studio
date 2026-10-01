// Validation questions (PRD §5.7.10): grouped by phase, and written out as Markdown for the
// offline SME session (Copy all · Download .md). Pure. The server has already hidden names.

import type { Question } from "./reviewTypes";

export const REASONS: Readonly<Record<string, string>> = {
  contested: "Contested",
  documented_only: "Documented only",
  inferred: "Inferred",
  partial_support: "Partial support",
  low_confidence: "Low confidence",
  gap: "Gap",
  gap_analysis: "Gap analysis",
  sequence: "Order not stated",
  not_described: "Not described",
};

/** Reasons shown in the danger outline; the others are neutral. */
export const DANGER_REASONS = new Set(["contested", "partial_support"]);

export const WHOLE_PROCESS = "Whole process";

/** Questions grouped by phase, in the order the phases first appear. */
export function byPhase(questions: readonly Question[]): { phase: string; questions: Question[] }[] {
  const groups = new Map<string, Question[]>();
  for (const q of questions) {
    const phase = q.phase_name || WHOLE_PROCESS;
    groups.set(phase, [...(groups.get(phase) ?? []), q]);
  }
  return [...groups].map(([phase, list]) => ({ phase, questions: list }));
}

/** The questions as Markdown: a title, then each phase with its numbered questions. */
export function questionsMarkdown(questions: readonly Question[], processName: string, versionLabel: string): string {
  const open = questions.filter((q) => q.status === "open").length;
  const lines = [
    `# Validation questions: ${processName || "process"}`,
    "",
    `Draft ${versionLabel}. ${open} of ${questions.length} questions open. For the session with the people who do the work.`,
  ];
  for (const group of byPhase(questions)) {
    lines.push("", `## ${group.phase}`, "");
    group.questions.forEach((q, i) => {
      const about = q.element_label ? ` (step: ${q.element_label})` : "";
      const reason = REASONS[q.reason] ?? q.reason;
      const answered = q.status === "answered" ? " [answered]" : "";
      lines.push(`${i + 1}. ${q.question}${about} · ${reason}${answered}`);
    });
  }
  return `${lines.join("\n")}\n`;
}

/** A file name for the download: "validation-questions-v0-1.md". */
export function questionsFileName(versionLabel: string): string {
  return `validation-questions-${versionLabel.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "").toLowerCase() || "draft"}.md`;
}
