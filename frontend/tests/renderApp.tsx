import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";
import { App } from "../src/App";
import { ToastProvider } from "../src/components/shell";

export interface FakeResponse {
  status?: number;
  body: unknown;
}

export type Handler = (body: unknown) => FakeResponse;

/** A fake backend: "METHOD /api/path" → handler. Unknown routes answer 404 in the standard shape. */
export function fakeApi(routes: Record<string, Handler>) {
  const calls: { key: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url}`;
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ key, body });
    const handler = routes[key];
    const result = handler
      ? handler(body)
      : { status: 404, body: { error: { code: "NOT_FOUND", message: "Not found.", details: {} } } };
    return new Response(JSON.stringify(result.body), {
      status: result.status ?? 200,
      headers: { "Content-Type": "application/json", "X-Request-ID": "req000000001" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

export function renderApp(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <ToastProvider>
          <App />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export const SETTINGS = {
  owner_name: "Owner",
  model: "claude-opus-5-5",
  effort: "high",
  verifier_enabled: true,
  web_research_enabled: false,
  key_set: false,
  key_last4: "",
};
