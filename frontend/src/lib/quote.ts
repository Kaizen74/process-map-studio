// Finding a cited quote inside a passage for the source viewer's highlight (PRD §5.7.8). The
// backend already checked the quote against the passage (G4); this only locates it for display,
// ignoring case, runs of spaces and curly versus straight quote marks. Pure.

const QUOTES: Readonly<Record<string, string>> = { "‘": "'", "’": "'", "“": '"', "”": '"' };

function normalise(text: string): { plain: string; at: number[] } {
  let plain = "";
  const at: number[] = []; // at[i] = index in `text` of plain[i]
  for (let i = 0; i < text.length; i += 1) {
    const raw = text.charAt(i);
    const ch = /\s/.test(raw) ? " " : (QUOTES[raw] ?? raw).toLowerCase();
    if (ch === " " && (plain === "" || plain.endsWith(" "))) continue;
    plain += ch;
    at.push(i);
  }
  return { plain, at };
}

/** [start, end) of `quote` in `text`, or null when it can't be found as written. */
export function quoteRange(text: string, quote: string): [number, number] | null {
  let needle = normalise(quote.trim()).plain.trim();
  if (/^["'].*["']$/.test(needle)) needle = needle.slice(1, -1); // quote marks around the whole quote
  if (!needle) return null;
  const { plain, at } = normalise(text);
  for (const candidate of [needle, needle.replace(/[.,;:!?]+$/, "")]) {
    const found = candidate ? plain.indexOf(candidate) : -1;
    if (found >= 0) {
      const start = at[found] ?? 0;
      const last = at[found + candidate.length - 1] ?? start;
      return [start, last + 1];
    }
  }
  return null;
}
