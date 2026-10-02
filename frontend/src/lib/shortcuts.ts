// Review keyboard shortcuts (PRD §5.8). Pure: a key press becomes an action or nothing. Every
// shortcut is ignored while a text input, select or textarea has focus, and with Ctrl, Alt or
// the Command key held (those belong to the browser).

import { isTyping } from "./keys";
import { LENSES, type Lens } from "./lens";

export type Shortcut =
  | { kind: "next" }
  | { kind: "previous" }
  | { kind: "confirm" }
  | { kind: "edit" }
  | { kind: "reject" }
  | { kind: "close" }
  | { kind: "lens"; lens: Lens }
  | { kind: "help" };

export interface KeyPress {
  key: string;
  target: EventTarget | null;
  ctrlKey: boolean;
  altKey: boolean;
  metaKey: boolean;
}

/** The shortcut list shown by "?". */
export const SHORTCUTS: readonly { keys: string; action: string }[] = [
  { keys: "J", action: "Next step in process order" },
  { keys: "K", action: "Previous step in process order" },
  { keys: "C", action: "Confirm the selected step as drafted" },
  { keys: "E", action: "Edit the selected step" },
  { keys: "R", action: "Reject the selected step" },
  { keys: "Esc", action: "Close the source, the edit form or this list" },
  { keys: "1 – 5", action: `Switch lens: ${LENSES.map((l) => l.label).join(", ")}` },
  { keys: "?", action: "Show this list" },
];

const LETTERS: Readonly<Record<string, Shortcut>> = {
  j: { kind: "next" },
  k: { kind: "previous" },
  c: { kind: "confirm" },
  e: { kind: "edit" },
  r: { kind: "reject" },
  "?": { kind: "help" },
  Escape: { kind: "close" },
};

export function shortcutFor(press: KeyPress): Shortcut | null {
  if (press.ctrlKey || press.altKey || press.metaKey || isTyping(press.target)) return null;
  const letter = LETTERS[press.key.length === 1 ? press.key.toLowerCase() : press.key];
  if (letter) return letter;
  const lens = /^[1-5]$/.test(press.key) ? LENSES[Number(press.key) - 1] : undefined;
  return lens ? { kind: "lens", lens: lens.value } : null;
}

/** J and K: the next or previous element in process order, from the selected one (or the ends). */
export function stepAlong(ids: readonly string[], current: string | null, direction: 1 | -1): string | null {
  if (ids.length === 0) return null;
  const at = current === null ? -1 : ids.indexOf(current);
  if (at === -1) return direction === 1 ? (ids[0] ?? null) : (ids[ids.length - 1] ?? null);
  const next = at + direction;
  return next < 0 || next >= ids.length ? (ids[at] ?? null) : (ids[next] ?? null);
}
