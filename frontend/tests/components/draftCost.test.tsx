import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DraftEstimate, DraftState, Settings } from "../../src/api/types";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp } from "../renderApp";

// Deep review item 5 (2026-10-19): what a draft will probably cost, shown before it starts, and
// the optional spending limit in Settings (API_CONTRACT.md → draft/estimate, settings/spending).

afterEach(() => vi.unstubAllGlobals());

const READY = { ...READINESS, key_set: true, transcripts_ready: true, documents_ready: true, missing: [] as string[], ready_to_draft: true };
const EMPTY: DraftState = { job: null, version: null, summary: null };
// The contract's example response.
const ESTIMATE: DraftEstimate = {
  sources: 6,
  characters: 48210,
  input_tokens: 48210,
  output_tokens: 24105,
  cost_usd: 0.67,
  basis: "assumed",
  drafts_measured: 0,
  model: "claude-opus-5-5",
  prices_checked_on: "2026-10-19",
  limit_usd: null,
  over_limit: false,
};
const COST_LIMIT = {
  status: 409,
  body: {
    error: {
      code: "COST_LIMIT",
      message: "This draft is estimated at about US$3.40, above your limit of US$2.00. Raise the limit in Settings, or draft from fewer sources.",
      details: { estimate_usd: 3.4, limit_usd: 2.0 },
    },
  },
};

function draftApi(estimate: Partial<DraftEstimate> | null, readiness = READY) {
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: readiness }),
    "GET /api/engagements/e1/draft": () => ({ body: EMPTY }),
    "GET /api/engagements/e1/draft/estimate": () =>
      estimate === null ? { status: 500, body: { error: { code: "IO", message: "The price list couldn't be read.", details: {} } } } : { body: { ...ESTIMATE, ...estimate } },
    "POST /api/engagements/e1/draft": () => COST_LIMIT,
  });
}

describe("Draft screen: cost estimate", () => {
  it("shows the estimate under Create draft map, how it was worked out and when prices were checked", async () => {
    draftApi({});
    const view = renderApp("/engagements/e1/draft");
    expect(
      await screen.findByText(
        "Estimated cost: about US$0.67 for 6 sources (a rough rule until your first real draft; prices checked 19 Oct 2026).",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/above your limit/)).not.toBeInTheDocument();
    expect(await seriousViolations(view.container)).toEqual([]);
  });

  it("says when the estimate is measured from earlier real drafts", async () => {
    draftApi({ basis: "measured", drafts_measured: 3, cost_usd: 1.2 });
    renderApp("/engagements/e1/draft");
    expect(await screen.findByText(/about US\$1\.20 for 6 sources \(based on your last 3 real drafts;/)).toBeInTheDocument();
  });

  it("warns before starting when the estimate is above the limit, and explains the refusal", async () => {
    const { calls } = draftApi({ cost_usd: 3.4, limit_usd: 2, over_limit: true });
    const view = renderApp("/engagements/e1/draft");
    const note = await screen.findByText(/That is above your limit of US\$2\.00, so the draft won't start\./);
    expect(within(note).getByRole("link", { name: "Open Settings" })).toHaveAttribute("href", "/settings");
    fireEvent.click(screen.getByRole("button", { name: "Create draft map" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("above your limit of US$2.00");
    expect(calls.filter((c) => c.key === "POST /api/engagements/e1/draft")).toHaveLength(1);
    expect(await seriousViolations(view.container)).toEqual([]);
  });

  it("says plainly when the model has no price, and never blocks on the limit then", async () => {
    draftApi({ cost_usd: null, model: "claude-new-model", limit_usd: 2 });
    renderApp("/engagements/e1/draft");
    expect(await screen.findByText("No cost estimate: the price of claude-new-model isn't in the app's price list.")).toBeInTheDocument();
    expect(screen.getByText(/can't be checked without a price, so it doesn't stop this draft/)).toBeInTheDocument();
  });

  it("keeps drafting available when the estimate can't be worked out", async () => {
    draftApi(null);
    renderApp("/engagements/e1/draft");
    expect(await screen.findByText("The cost of this draft couldn't be estimated. Drafting still works.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create draft map" })).toBeInTheDocument();
  });

  it("asks for no estimate until the draft can start", async () => {
    const { calls } = draftApi({}, { ...READY, ready_to_draft: false, missing: ["Add at least one interview transcript"] });
    renderApp("/engagements/e1/draft");
    expect(await screen.findByText("Add at least one interview transcript")).toBeInTheDocument();
    expect(calls.some((c) => c.key === "GET /api/engagements/e1/draft/estimate")).toBe(false);
  });
});

function settingsApi(start: Partial<Settings> = {}) {
  let current: Settings = { ...(SETTINGS as Settings), ...start };
  return fakeApi({
    "GET /api/settings": () => ({ body: current }),
    "PUT /api/settings/spending": (body) => {
      current = { ...current, ...(body as Partial<Settings>) };
      return { body: current };
    },
    "GET /api/settings/usage": () => ({ body: { items: [], totals: { calls: 0, input_tokens: 0, output_tokens: 0, web_searches: 0 } } }),
    "GET /api/health": () => ({ body: { status: "ok", app_version: "1.0.0", prd_version: "1.12" } }),
  });
}

const spendingCard = async () =>
  (await screen.findByRole("heading", { name: "AI spending" })).closest("section") as HTMLElement;

describe("Settings: AI spending", () => {
  it("saves a limit and clears it again", async () => {
    const { calls } = settingsApi();
    const view = renderApp("/settings");
    const card = await spendingCard();
    const field = within(card).getByRole("textbox", { name: "Most to spend on one draft (US$)" });
    expect(field).toHaveValue("");
    fireEvent.change(field, { target: { value: "US$2.5" } });
    fireEvent.click(within(card).getByRole("button", { name: "Save spending limit" }));
    expect(await screen.findByText("Your spending limit was saved.")).toBeInTheDocument();
    expect(field).toHaveValue("2.50");
    fireEvent.change(field, { target: { value: " " } });
    fireEvent.click(within(card).getByRole("button", { name: "Save spending limit" }));
    expect(await screen.findByText("No spending limit is set.")).toBeInTheDocument();
    const saved = calls.filter((c) => c.key === "PUT /api/settings/spending").map((c) => c.body);
    expect(saved).toEqual([{ draft_cost_limit_usd: 2.5 }, { draft_cost_limit_usd: null }]);
    expect(await seriousViolations(view.container)).toEqual([]);
  });

  it("shows a saved limit and explains an amount out of range before sending anything", async () => {
    const { calls } = settingsApi({ draft_cost_limit_usd: 5 });
    renderApp("/settings");
    const card = await spendingCard();
    const field = within(card).getByRole("textbox", { name: "Most to spend on one draft (US$)" });
    expect(field).toHaveValue("5.00");
    for (const value of ["0", "-5", "1000.01", "five"]) {
      fireEvent.change(field, { target: { value } });
      fireEvent.click(within(card).getByRole("button", { name: "Save spending limit" }));
      await waitFor(() =>
        expect(within(card).getByText("Enter an amount above 0 and up to 1,000, or leave it empty for no limit.")).toBeInTheDocument(),
      );
    }
    expect(calls.some((c) => c.key === "PUT /api/settings/spending")).toBe(false);
  });
});
