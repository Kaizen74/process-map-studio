// The coverage report (API_CONTRACT.md → GET /versions/{vid}/coverage; PRD §3.12.8, criterion 50):
// what the interviews covered and the follow-up questions still to ask. Shared by the API layer
// and the components (components never import src/api).

export type CoverageStatus = "covered" | "thin" | "missing";

export interface CoverageDimension {
  status: CoverageStatus;
  evidence_count: number;
  note: string;
}

export interface FollowUpQuestion {
  dimension: string;
  question_id: string;
  question: string;
  about: string;
}

export interface ReflectiveProbe {
  question_id: string;
  question: string;
  quote: string;
  source_id: string;
  anchor: string;
  speaker_role: string;
}

export interface CoverageReport {
  version_id: string;
  dimensions: Record<string, CoverageDimension>;
  follow_up_questions: FollowUpQuestion[];
  probes: ReflectiveProbe[];
}

/** The dimensions in the report's order, with their plain names. */
export const DIMENSIONS: readonly { key: string; label: string }[] = [
  { key: "trigger", label: "Trigger" },
  { key: "end_point", label: "End point" },
  { key: "step_spine", label: "Step spine" },
  { key: "handoffs", label: "Handoffs" },
  { key: "decisions_and_criteria", label: "Decisions and criteria" },
  { key: "approvals", label: "Approvals" },
  { key: "exceptions", label: "Exceptions" },
  { key: "raci", label: "RACI" },
  { key: "work_and_wait_time", label: "Work and wait time" },
  { key: "kpis", label: "KPIs" },
  { key: "artefacts", label: "Artefacts" },
  { key: "know_how", label: "Know-how at each decision" },
  { key: "stories", label: "Stories" },
  { key: "official_vs_lived", label: "Official vs lived" },
  { key: "sme_terms", label: "SME terms" },
];

export function dimensionLabel(key: string): string {
  return DIMENSIONS.find((d) => d.key === key)?.label ?? key.replaceAll("_", " ");
}

/** One follow-up question as printed: "[M2.1] … (about Draft load plan)". */
export function followUpLine(q: { question_id: string; question: string; about?: string }): string {
  return `[${q.question_id}] ${q.question}${q.about ? ` (about ${q.about})` : ""}`;
}

/** The ready-to-ask follow-up questions, for Copy and Download .md (a 20–30 minute Follow-up). */
export function followUpMarkdown(report: CoverageReport, mapLabel: string): string {
  const lines = [
    `# Follow-up questions (${mapLabel})`,
    "",
    "For a 20–30 minute Follow-up interview. Say or note the question ID when you ask it. Use roles, not names.",
  ];
  if (report.follow_up_questions.length > 0) {
    lines.push("", "## What the interviews covered thinly or not at all", "");
    for (const q of report.follow_up_questions) {
      const status = report.dimensions[q.dimension]?.status ?? "";
      lines.push(`- ${followUpLine(q)} — ${dimensionLabel(q.dimension)}${status ? `: ${status}` : ""}`);
    }
  }
  if (report.probes.length > 0) {
    lines.push("", "## In the interviewee's own words", "");
    for (const p of report.probes) lines.push(`- ${followUpLine(p)}`);
  }
  if (report.follow_up_questions.length === 0 && report.probes.length === 0) {
    lines.push("", "Nothing left to ask: every dimension is covered.");
  }
  return lines.join("\n") + "\n";
}

export function followUpFileName(mapLabel: string): string {
  return `follow-up-questions-${mapLabel.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}.md`;
}
