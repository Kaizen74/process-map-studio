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

/** The Capability Compass return file of a published version, with the cells Eric added. */
export function compassReturnUrl(versionId: string, format: "json" | "md", cells: readonly string[]): string {
  const extra = cells.length ? `&cells=${cells.map(encodeURIComponent).join(",")}` : "";
  return `/api/versions/${encodeURIComponent(versionId)}/compass-return?fmt=${format}${extra}`;
}

export const RETURN_EXCLUDED =
  "Role names only. No quotes, no source text, no names on your list of names to hide and no API key.";

export function exportUrl(versionId: string, format: ExportFormat): string {
  return `/api/versions/${encodeURIComponent(versionId)}/export/${format}`;
}

// The Reality pack of a published version (PRD §3.18.6, §7.4; P13d): one offline HTML file of the
// seven Reality views, laid out for A3 landscape or 16:9 slide pages, from
// `GET /api/versions/{vid}/reality/export?layout=a3|slide`.

export type PackLayout = "a3" | "slide";

export const PACK_LAYOUTS: readonly { layout: PackLayout; label: string }[] = [
  { layout: "a3", label: "A3" },
  { layout: "slide", label: "16:9" },
];

export const PACK_EXCLUDED = "Role names only; no images, interview quotes or names.";

export function realityPackUrl(versionId: string, layout: PackLayout): string {
  return `/api/versions/${encodeURIComponent(versionId)}/reality/export?layout=${layout}`;
}
