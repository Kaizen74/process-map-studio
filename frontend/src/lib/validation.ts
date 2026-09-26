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
