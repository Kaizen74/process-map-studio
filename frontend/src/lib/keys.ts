// Keyboard rules shared by the Review screen (PRD §5.8): every shortcut, Esc included, is
// ignored while a text input, select or textarea has focus.

const TEXT_INPUTS = new Set(["text", "search", "email", "number", "password", "tel", "url", ""]);

/** True when the key press is someone typing into a field, so shortcuts leave it alone. */
export function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  if (tag === "TEXTAREA" || tag === "SELECT") return true;
  if (tag !== "INPUT") return false;
  return TEXT_INPUTS.has((target.getAttribute("type") ?? "").toLowerCase());
}
