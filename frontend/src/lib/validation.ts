// Field rules shared by forms (PRD §5.11). Messages match the backend's (actions/settings.py)
// so the owner sees the same sentence whether the check runs here or on the server.

export const OWNER_NAME_MESSAGE = "Please enter your name (up to 80 characters, no line breaks).";
export const API_KEY_MESSAGE =
  "That doesn't look like a Claude API key. Keys start with sk-ant-. Copy it again from the Claude Console.";

/** null when valid, otherwise the message to show under the field. */
export function validateOwnerName(value: string): string | null {
  const name = value.trim();
  if (!name || name.length > 80 || /[\r\n\t]/.test(name)) return OWNER_NAME_MESSAGE;
  return null;
}

export function validateApiKey(value: string): string | null {
  return /^sk-ant-[A-Za-z0-9_-]{13,293}$/.test(value.trim()) ? null : API_KEY_MESSAGE;
}

export const ENGAGEMENT_NAME_MESSAGE = "Please give the engagement a name (up to 120 characters).";

export function validateEngagementName(value: string): string | null {
  const name = value.trim();
  if (!name || name.length > 120 || /[\r\n]/.test(name)) return ENGAGEMENT_NAME_MESSAGE;
  return null;
}

// Scope-card rules (API_CONTRACT.md → Engagements): the same limits the server applies.
export const TEXT_LIMIT = 2000;
export const LIST_LIMIT = 50;
export const ITEM_LIMIT = 120;

export function validateScopeText(label: string, value: string): string | null {
  return value.trim().length > TEXT_LIMIT ? `${label}: at most ${TEXT_LIMIT} characters.` : null;
}

export function validateScopeList(label: string, values: readonly string[]): string | null {
  if (values.length > LIST_LIMIT) return `${label}: at most ${LIST_LIMIT} entries.`;
  if (values.some((v) => v.length > ITEM_LIMIT)) return `${label}: each entry must be one line of up to ${ITEM_LIMIT} characters.`;
  return null;
}

export const ROLE_NAME_MESSAGE = "Please give the role a name (up to 80 characters).";

export function validateRoleName(value: string): string | null {
  const name = value.trim();
  return !name || name.length > 80 || /[\r\n]/.test(name) ? ROLE_NAME_MESSAGE : null;
}
