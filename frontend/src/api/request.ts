// The one typed request wrapper (PRD §3.2): JSON in and out, the standard error shape
// {"error": {"code", "message", "details"}} turned into ApiError, and the request ID kept for
// "Copy details". Only src/hooks/ may call the api/ modules.

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;
  readonly requestId: string;

  constructor(
    code: string,
    message: string,
    status: number,
    details: Record<string, unknown>,
    requestId: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
    this.requestId = requestId;
  }

  /** "Copy details" text for bug reports: error code and request ID. */
  get copyText(): string {
    return this.requestId ? `${this.code} · request ${this.requestId}` : this.code;
  }
}

export const SERVER_NOT_ANSWERING =
  "The app's server isn't answering. Make sure the Process Map Studio window is still open, then try again.";

interface ErrorBody {
  error?: { code?: unknown; message?: unknown; details?: unknown };
}

export async function request<T>(
  path: string,
  options: { method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"; body?: unknown } = {},
): Promise<T> {
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers: { Accept: "application/json" },
  };
  if (options.body !== undefined) {
    init.headers = { ...init.headers, "Content-Type": "application/json" };
    init.body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError("NETWORK", SERVER_NOT_ANSWERING, 0, {}, "");
  }

  const headerId = response.headers.get("X-Request-ID") ?? "";
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const error = (data as ErrorBody | null)?.error;
    const details =
      error && typeof error.details === "object" && error.details !== null
        ? (error.details as Record<string, unknown>)
        : {};
    const requestId = typeof details.request_id === "string" ? details.request_id : headerId;
    throw new ApiError(
      typeof error?.code === "string" ? error.code : `HTTP_${response.status}`,
      typeof error?.message === "string"
        ? error.message
        : "Something went wrong inside the app. Try again, or use Copy details to report it.",
      response.status,
      details,
      requestId,
    );
  }
  return data as T;
}
