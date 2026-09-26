// Display formats shared by screens (PRD §5.3 "Numbers and times": mono font is applied by CSS).

// Fixed month names: Intl output differs between browsers ("Sep" or "Sept").
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "26 Sep 2026" (local date) from an ISO timestamp; the raw text if it can't be read. */
export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${date.getDate()} ${MONTHS[date.getMonth()] ?? ""} ${date.getFullYear()}`;
}

/** "1 source", "3 sources". */
export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** Sentence case for a single word state, e.g. "draft" → "Draft". */
export function sentence(text: string): string {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

/** "26 Sep 2026, 10:02" (local time) from an ISO timestamp; the raw text if it can't be read. */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${formatDate(iso)}, ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
