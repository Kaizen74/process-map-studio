import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Settings } from "../../src/api/types";
import { zoneOptions } from "../../src/lib/systemRecords";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp } from "../renderApp";

// R10 (PRD §3.4 items 9-10, §5.4 Settings; decision A): the Regional card, the full Optional
// modules card, Gap analysis behind its switch, and a new log starting in the default time zone.

afterEach(() => vi.unstubAllGlobals());

function settingsApi(start: Partial<Settings> = {}) {
  let current: Settings = { ...(SETTINGS as Settings), ...start };
  return fakeApi({
    "GET /api/settings": () => ({ body: current }),
    "PUT /api/settings/modules": (body) => {
      current = { ...current, ...(body as Partial<Settings>) };
      return { body: current };
    },
    "PUT /api/settings/regional": (body) => {
      const b = body as Partial<Settings>;
      if (b.default_timezone === "Mars/Olympus") {
        return { status: 422, body: { error: { code: "VALIDATION", details: { field: "default_timezone" },
          message: "Choose a time zone from the list, for example Asia/Singapore." } } }; // prettier-ignore
      }
      current = { ...current, ...b };
      return { body: current };
    },
    "GET /api/settings/usage": () => ({ body: { items: [], totals: { calls: 0, input_tokens: 0, output_tokens: 0, web_searches: 0 } } }),
    "GET /api/health": () => ({ body: { status: "ok", app_version: "1.0.0", prd_version: "1.12" } }),
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/versions": () => ({ body: [] }),
    "GET /api/engagements/e1/event-logs": () => ({ body: [] }),
    "GET /api/engagements/e1/roles": () => ({ body: [] }),
  });
}

const card = async (title: string) =>
  (await screen.findByRole("heading", { name: title })).closest("section") as HTMLElement;

describe("Settings: Regional (R10)", () => {
  it("shows the currency and default time zone and saves them together", async () => {
    const { calls } = settingsApi();
    const view = renderApp("/settings");
    const regional = await card("Regional");
    const currency = within(regional).getByRole("textbox", { name: "Currency" });
    expect(currency).toHaveValue("SGD");
    expect(within(regional).getByRole("combobox", { name: "Default time zone for system logs" })).toHaveValue("Asia/Singapore");
    fireEvent.change(currency, { target: { value: "eur" } });
    fireEvent.change(within(regional).getByRole("combobox"), { target: { value: "Europe/Paris" } });
    fireEvent.click(within(regional).getByRole("button", { name: "Save regional settings" }));
    expect(await screen.findByText("Regional settings were saved.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PUT /api/settings/regional")?.body).toEqual({
      currency: "EUR",
      default_timezone: "Europe/Paris",
    });
    expect(await seriousViolations(view.container)).toEqual([]);
  });

  it("explains a wrong currency code before sending anything", async () => {
    const { calls } = settingsApi();
    renderApp("/settings");
    const regional = await card("Regional");
    fireEvent.change(within(regional).getByRole("textbox", { name: "Currency" }), { target: { value: "dollars" } });
    fireEvent.click(within(regional).getByRole("button", { name: "Save regional settings" }));
    expect(await within(regional).findByText("Enter a three-letter currency code, for example SGD.")).toBeInTheDocument();
    expect(calls.some((c) => c.key === "PUT /api/settings/regional")).toBe(false);
  });

  it("keeps a time zone that isn't in the short list", () => {
    expect(zoneOptions("America/Sao_Paulo")[0]).toEqual({ value: "America/Sao_Paulo", label: "America/Sao Paulo" });
    expect(zoneOptions("Asia/Singapore")[0]?.value).toBe("Asia/Singapore");
  });
});

describe("Settings: Optional modules (R10)", () => {
  it("lists gap analysis (on), system records and the value calculator (off), and saves each switch", async () => {
    const { calls } = settingsApi();
    renderApp("/settings");
    const modules = await card("Optional modules");
    const gap = within(modules).getByRole("checkbox", { name: "Gap analysis" });
    const value = within(modules).getByRole("checkbox", { name: "Value calculator and step dispositions" });
    expect([gap, within(modules).getByRole("checkbox", { name: "System records" }), value].map((b) => (b as HTMLInputElement).checked)).toEqual([true, false, false]); // prettier-ignore
    fireEvent.click(value);
    expect(await screen.findByText("Value calculator and step dispositions switched on.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PUT /api/settings/modules")?.body).toEqual({ value_enabled: true });
    await waitFor(() => expect(value).toBeChecked());
  });
});

describe("Gap analysis behind its switch (R10)", () => {
  it("leaves the nav while off and the screen says so, keeping earlier analyses", async () => {
    settingsApi({ gap_analysis_enabled: false });
    renderApp("/engagements/e1/gap-analysis");
    expect(await screen.findByText(/Gap analysis is switched off/)).toBeInTheDocument();
    expect(screen.getByText(/Earlier analyses are kept/)).toBeInTheDocument();
    const steps = await screen.findByRole("navigation", { name: "Engagement steps" });
    await waitFor(() => expect(within(steps).queryByRole("link", { name: /Gap analysis/ })).toBeNull());
  });

  it("stays in the nav, labelled optional, while on (the default)", async () => {
    settingsApi();
    renderApp("/engagements/e1/setup");
    const steps = await screen.findByRole("navigation", { name: "Engagement steps" });
    expect(await within(steps).findByRole("link", { name: /^Gap analysis/ })).toBeInTheDocument();
  });
});

describe("System records upload (R10)", () => {
  it("starts with the default time zone from Settings", async () => {
    settingsApi({ system_records_enabled: true, default_timezone: "Europe/London" });
    renderApp("/engagements/e1/system-records");
    const upload = await card("Upload a log");
    await waitFor(() => expect(within(upload).getByRole("combobox", { name: /Time zone/ })).toHaveValue("Europe/London"));
  });
});
