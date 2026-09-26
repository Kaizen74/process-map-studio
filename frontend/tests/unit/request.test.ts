import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, SERVER_NOT_ANSWERING, request } from "../../src/api/request";

function respond(status: number, body: unknown, requestId = "abc123def456") {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      typeof body === "string"
        ? new Response(body, { status, headers: { "X-Request-ID": requestId } })
        : new Response(JSON.stringify(body), { status, headers: { "X-Request-ID": requestId } }),
    ),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("request()", () => {
  it("returns JSON and sends JSON bodies to /api", async () => {
    respond(200, { ok: true });
    await expect(request("/settings/profile", { method: "PUT", body: { owner_name: "E" } })).resolves.toEqual({ ok: true });
    const [url, init] = vi.mocked(fetch).mock.calls[0] ?? [];
    expect(url).toBe("/api/settings/profile");
    expect(init?.method).toBe("PUT");
    expect(init?.body).toBe('{"owner_name":"E"}');
  });

  it("turns the standard error shape into ApiError with Copy details", async () => {
    respond(409, {
      error: { code: "PUBLISH_BLOCKED", message: "Publishing is blocked.", details: { request_id: "fromBody0001" } },
    });
    const error = await request("/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "PUBLISH_BLOCKED", status: 409, message: "Publishing is blocked." });
    expect((error as ApiError).copyText).toBe("PUBLISH_BLOCKED · request fromBody0001");
  });

  it("falls back to the header request ID and a plain message for odd errors", async () => {
    respond(502, "<html>bad gateway</html>", "hdr000000001");
    const error = (await request("/x").catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("HTTP_502");
    expect(error.message).toMatch(/Something went wrong/);
    expect(error.copyText).toBe("HTTP_502 · request hdr000000001");
  });

  it("explains when the server isn't answering", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    const error = (await request("/x").catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("NETWORK");
    expect(error.message).toBe(SERVER_NOT_ANSWERING);
    expect(error.copyText).toBe("NETWORK");
  });
});
