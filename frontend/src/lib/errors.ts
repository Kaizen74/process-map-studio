// Plain-language error helpers shared by every screen (PRD §5.3 error pattern).

/** "Copy details" text for an error: the code and request ID when the app's API supplied them. */
export function copyDetailsOf(error: unknown): string | undefined {
  if (error && typeof error === "object" && "copyText" in error) {
    const text = (error as { copyText: unknown }).copyText;
    return typeof text === "string" && text ? text : undefined;
  }
  return undefined;
}

/** A message safe to show: the API's plain message, or a generic sentence. */
export function messageOf(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return "Something went wrong. Try again, or use Copy details to report it.";
}
