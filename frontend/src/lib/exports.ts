// The four exports of a published version (PRD §5.4 Exports, §7.3). Downloads are plain links to
// `GET /api/versions/{vid}/export/{fmt}`: the browser saves the file the server names.

export type ExportFormat = "md" | "json" | "csv" | "html";

export interface ExportKind {
  format: ExportFormat;
  title: string;
  description: string;
}

export const EXPORTS: readonly ExportKind[] = [
  {
    format: "md",
    title: "Master Process Map (.md)",
    description: "The full write-up: facts, interpretation and recommendation, in the fixed template.",
  },
  {
    format: "json",
    title: "Graph (.json)",
    description: "The map as data, with its quality card, for other tools and skills.",
  },
  {
    format: "csv",
    title: "RACI (.csv)",
    description: "Every step against every role, ready for a spreadsheet.",
  },
  {
    format: "html",
    title: "Interactive map (.html)",
    description: "The swimlane map in one file that opens in any browser, offline.",
  },
];

export const EXCLUDED = "No images, verbatim quotes or names.";

export function exportUrl(versionId: string, format: ExportFormat): string {
  return `/api/versions/${encodeURIComponent(versionId)}/export/${format}`;
}
