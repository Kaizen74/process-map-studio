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

export type Handler = (body: unknown, url: string) => FakeResponse;

/** Steps and versions have no pictures unless a test gives them some (phase P8). */
const NO_PICTURES = /^GET \/api\/(elements|versions)\/[^/]+\/images$/;
const PLANS = "GET /api/templates/interview/plans";

/** The standard interview templates (always available; PRD v1.10 F.9), as the backend lists them. */
export const TEMPLATE_PLANS = [
  {
    type: "landscape",
    title: "Landscape",
    minutes: 60,
    who: "Team leads, contract holders, cross-functional owners (one per stakeholder group lead)",
    purpose: "The end-to-end picture: which teams, how structured, what each manages",
    plan: [
      { label: "Opener and framing", minutes: 3 },
      { label: "L1–L2 teams, structure, activities", minutes: 10 },
      { label: "L3–L5 interfaces, decision rights, boundaries", minutes: 20 },
      { label: "Role module (3–5 blank rows for the stakeholder group)", minutes: 8 },
      { label: "L6–L7 strengths, weaknesses, risk", minutes: 8 },
      { label: "Two stories with signifiers (M5.1–M5.2, M5.s1–s3)", minutes: 7 },
      { label: "Close (M7.1, M7.5, M7.6)", minutes: 4 },
    ],
    question_count: 16,
    bank_version: "1.0",
  },
  {
    type: "practice",
    title: "Practice",
    minutes: 60,
    who: "People who do the work (one per person)",
    purpose: "The workflow as actually performed: steps, decisions, know-how, variations, official vs lived",
    plan: [
      { label: "M0 — Framing", minutes: 3 },
      { label: "M1 — Open conversation", minutes: 6 },
      { label: "M2 — The last real case: the As done spine", minutes: 14 },
      { label: "M3 — Artefact walk-through (with the completed examples)", minutes: 6 },
      { label: "M4 — Decisions: decision mapping and ASHEN", minutes: 12 },
      { label: "M5 — Stories: prompting questions and the SME's own reading of them", minutes: 9 },
      { label: "M6 — Contrast: official vs lived; now bring the documents", minutes: 6 },
      { label: "M7 — Close: ask only what is still missing", minutes: 4 },
    ],
    question_count: 45,
    bank_version: "1.0",
  },
  {
    type: "follow_up",
    title: "Follow-up",
    minutes: 30,
    who: "Anyone already interviewed",
    purpose: "Close gaps and test interpretations using the SME's own words",
    plan: [
      { label: "Opener", minutes: 2 },
      { label: "F-series with blank rows for reflective probes", minutes: 22 },
      { label: "Close", minutes: 6 },
    ],
    question_count: 13,
    bank_version: "1.0",
  },
];

/**
 * A fake backend: "METHOD /api/path" → handler. Unknown routes answer 404 in the standard shape,
 * except a step's or version's pictures, which default to none, and the interview templates.
 */
export function fakeApi(routes: Record<string, Handler>) {
  const calls: { key: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url.split("?")[0] ?? url}`;
    const body =
      init?.body instanceof FormData ? init.body : init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ key, body });
    const handler = routes[key];
    const result = handler
      ? handler(body, url)
      : NO_PICTURES.test(key)
        ? { body: [] }
        : key === PLANS
          ? { body: TEMPLATE_PLANS }
          : { status: 404, body: { error: { code: "NOT_FOUND", message: "Not found.", details: {} } } };
    if (result.status === 204) return new Response(null, { status: 204, headers: { "X-Request-ID": "req000000001" } });
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
  system_records_enabled: false,
  gap_analysis_enabled: true,
  value_enabled: false,
  reality_views_enabled: false,
  currency: "SGD",
  default_timezone: "Asia/Singapore",
  key_set: false,
  key_last4: "",
};

export const ENGAGEMENT = {
  id: "e1",
  name: "Load control",
  process_name: "Aircraft load control",
  trigger: "",
  end_point: "",
  in_scope_roles: [],
  out_of_scope: "",
  process_kpi: "",
  industry: "",
  adjacent_industries: [],
  confidential_terms: [],
  status: "active",
  created_at: "2026-09-26T09:00:00+00:00",
  updated_at: "2026-09-26T10:00:00+00:00",
};

export const SUMMARY = {
  ...ENGAGEMENT,
  latest_version: null,
  review_progress: { reviewed: 0, total: 0 },
  sources_count: 0,
};

const NAV_KEYS = [
  "setup",
  "interview",
  "sources",
  "draft",
  "review",
  "published",
  "matrix",
  "gap_analysis",
  "registers",
  "leadership",
  "exports",
] as const;

export const READINESS = {
  key_set: false,
  transcripts_ready: false,
  documents_ready: false,
  speakers_unmapped: 0,
  draft_exists: false,
  blockers_count: 0,
  nav: Object.fromEntries(NAV_KEYS.map((k) => [k, "not_started"])),
  nav_counts: {},
  next_step: "setup",
  missing: ["Add your Claude API key in Settings", "Add an interview transcript"],
  ready_to_draft: false,
};
