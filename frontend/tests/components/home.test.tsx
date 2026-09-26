import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, SETTINGS, SUMMARY, fakeApi, renderApp } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

const KEYED = { ...SETTINGS, key_set: true, key_last4: "Zq9x" };
const DRAFTED = {
  ...SUMMARY,
  latest_version: { label: "v0.1", state: "draft" },
  review_progress: { reviewed: 4, total: 10 },
  sources_count: 2,
};

describe("Home (Engagements) with the first-run checklist", () => {
  it("asks for the API key first, linking to Settings", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: SETTINGS }),
      "GET /api/engagements": () => ({ body: [] }),
    });
    renderApp("/");
    expect(screen.getByRole("heading", { level: 1, name: "Engagements" })).toBeInTheDocument();
    await screen.findByText(/0 of 3 steps done/);
    const checklist = screen.getByRole("region", { name: "Get started" });
    const link = within(checklist).getByRole("link", { name: "Add your Claude API key" });
    expect(link).toHaveAttribute("href", "/settings");
    expect(within(checklist).getAllByText("To do")).toHaveLength(3);
    expect(screen.getAllByRole("button", { name: "New engagement" })).toHaveLength(1);
  });

  it("ticks the key step once a key is saved, showing only its last 4 characters", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: KEYED }),
      "GET /api/engagements": () => ({ body: [] }),
    });
    renderApp("/");
    await screen.findByText(/1 of 3 steps done/);
    const checklist = screen.getByRole("region", { name: "Get started" });
    expect(checklist).toHaveTextContent("Key saved (ending Zq9x)");
    expect(within(checklist).getByText("Done")).toBeInTheDocument();
  });

  it("ticks creating an engagement and links to uploading its sources", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: SETTINGS }),
      "GET /api/engagements": () => ({ body: [SUMMARY] }),
    });
    renderApp("/");
    await screen.findByText(/1 of 3 steps done/);
    const checklist = screen.getByRole("region", { name: "Get started" });
    expect(within(checklist).getByRole("link", { name: "Upload sources" })).toHaveAttribute(
      "href",
      "/engagements/e1/sources",
    );
  });

  it("hides the checklist once the key is saved and an engagement exists", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: KEYED }),
      "GET /api/engagements": () => ({ body: [DRAFTED] }),
    });
    renderApp("/");
    await screen.findByRole("link", { name: "Load control" });
    expect(screen.queryByRole("region", { name: "Get started" })).not.toBeInTheDocument();
  });

  it("shows a plain error with Copy details when settings can't load", async () => {
    fakeApi({
      "GET /api/settings": () => ({
        status: 500,
        body: { error: { code: "IO", message: "Your settings couldn't be read.", details: { request_id: "r9" } } },
      }),
      "GET /api/engagements": () => ({ body: [] }),
    });
    renderApp("/");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Your settings couldn't be loaded");
    expect(alert).toHaveTextContent("Your settings couldn't be read.");
    expect(within(alert).getByRole("button", { name: "Copy details" })).toBeInTheDocument();
    expect(within(alert).getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows a plain error when engagements can't load", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: KEYED }),
      "GET /api/engagements": () => ({
        status: 500,
        body: { error: { code: "INTERNAL", message: "Something went wrong inside the app.", details: {} } },
      }),
    });
    renderApp("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Your engagements couldn't be loaded");
  });

  it("shows skeletons while loading", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));
    renderApp("/");
    expect(document.querySelector("[aria-busy='true']")).not.toBeNull();
  });

  it("has no serious or critical accessibility violations", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: SETTINGS }),
      "GET /api/engagements": () => ({ body: [] }),
    });
    const { container } = renderApp("/");
    await screen.findByText(/steps done/);
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("unknown pages say so and link home", async () => {
    fakeApi({});
    renderApp("/no-such-page");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Engagements" })).toHaveAttribute("href", "/");
  });
});

describe("Engagement cards", () => {
  it("show name, version, review progress, sources and last updated", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: KEYED }),
      "GET /api/engagements": () => ({ body: [DRAFTED] }),
    });
    renderApp("/");
    const link = await screen.findByRole("link", { name: "Load control" });
    expect(link).toHaveAttribute("href", "/engagements/e1");
    const card = link.closest("article");
    expect(card).not.toBeNull();
    const text = card?.textContent ?? "";
    expect(text).toContain("Draft v0.1");
    expect(text).toContain("Aircraft load control");
    expect(text).toMatch(/4 of 10 reviewed/);
    expect(text).toContain("2 sources");
    expect(text).toContain("26 Sep 2026");
  });

  it("say when no draft exists yet", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: KEYED }),
      "GET /api/engagements": () => ({ body: [{ ...SUMMARY, sources_count: 1 }] }),
    });
    renderApp("/");
    await screen.findByText("No draft yet");
    expect(screen.getByText(/1 source · last updated/)).toBeInTheDocument();
    expect(screen.getByText("Nothing to review until the first draft.")).toBeInTheDocument();
  });

  it("have no serious or critical accessibility violations", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: KEYED }),
      "GET /api/engagements": () => ({ body: [DRAFTED, { ...SUMMARY, id: "e2", name: "Ramp" }] }),
    });
    const { container } = renderApp("/");
    await screen.findByRole("link", { name: "Ramp" });
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("New engagement", () => {
  it("explains a missing name instead of creating", async () => {
    const { calls } = fakeApi({
      "GET /api/settings": () => ({ body: SETTINGS }),
      "GET /api/engagements": () => ({ body: [] }),
    });
    renderApp("/");
    fireEvent.click(await screen.findByRole("button", { name: "New engagement" }));
    const dialog = screen.getByRole("dialog", { name: "New engagement" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Create engagement" }));
    expect(await within(dialog).findByText(/Please give the engagement a name/)).toBeInTheDocument();
    expect(calls.some((c) => c.key === "POST /api/engagements")).toBe(false);
  });

  it("creates the engagement and opens its Setup screen", async () => {
    const { calls } = fakeApi({
      "GET /api/settings": () => ({ body: SETTINGS }),
      "GET /api/engagements": () => ({ body: [] }),
      "POST /api/engagements": () => ({ status: 201, body: ENGAGEMENT }),
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/roles": () => ({ body: [] }),
    });
    renderApp("/");
    fireEvent.click(await screen.findByRole("button", { name: "New engagement" }));
    const dialog = screen.getByRole("dialog", { name: "New engagement" });
    fireEvent.change(within(dialog).getByLabelText("Engagement name"), { target: { value: "  Load control " } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Create engagement" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Setup" })).toBeInTheDocument();
    expect(calls.find((c) => c.key === "POST /api/engagements")?.body).toEqual({ name: "Load control" });
    expect(screen.getByText("Engagement created.")).toBeInTheDocument();
  });

  it("shows the server's message when creating fails", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: SETTINGS }),
      "GET /api/engagements": () => ({ body: [] }),
      "POST /api/engagements": () => ({
        status: 422,
        body: { error: { code: "VALIDATION", message: "Please give the engagement a name (up to 120 characters).", details: {} } },
      }),
    });
    renderApp("/");
    fireEvent.click(await screen.findByRole("button", { name: "New engagement" }));
    const dialog = screen.getByRole("dialog", { name: "New engagement" });
    fireEvent.change(within(dialog).getByLabelText("Engagement name"), { target: { value: "x" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Create engagement" }));
    expect(await within(dialog).findByText(/up to 120 characters/)).toBeInTheDocument();
  });
});

describe("Deleting an engagement", () => {
  it("names exactly what will be removed, then deletes it", async () => {
    let list = [DRAFTED];
    const { calls } = fakeApi({
      "GET /api/settings": () => ({ body: KEYED }),
      "GET /api/engagements": () => ({ body: list }),
      "DELETE /api/engagements/e1": () => {
        list = [];
        return { status: 204, body: null };
      },
    });
    renderApp("/");
    fireEvent.click(await screen.findByRole("button", { name: "Delete Load control" }));
    const dialog = screen.getByRole("dialog", { name: "Delete “Load control”?" });
    expect(dialog).toHaveTextContent("its 2 source files");
    expect(dialog).toHaveTextContent("can't be undone");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete engagement" }));
    expect(await screen.findByText("Engagement deleted.")).toBeInTheDocument();
    expect(calls.some((c) => c.key === "DELETE /api/engagements/e1")).toBe(true);
    expect(await screen.findByText(/No engagements yet/)).toBeInTheDocument();
  });

  it("Cancel keeps the engagement", async () => {
    const { calls } = fakeApi({
      "GET /api/settings": () => ({ body: KEYED }),
      "GET /api/engagements": () => ({ body: [DRAFTED] }),
    });
    renderApp("/");
    fireEvent.click(await screen.findByRole("button", { name: "Delete Load control" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(calls.some((c) => c.key.startsWith("DELETE"))).toBe(false);
  });

  it("explains a partial delete in plain words", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: KEYED }),
      "GET /api/engagements": () => ({ body: [DRAFTED] }),
      "DELETE /api/engagements/e1": () => ({
        status: 500,
        body: { error: { code: "IO", message: "The engagement was deleted, but some of its files couldn't be removed.", details: {} } },
      }),
    });
    renderApp("/");
    fireEvent.click(await screen.findByRole("button", { name: "Delete Load control" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete engagement" }));
    const dialog = screen.getByRole("dialog");
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("some of its files couldn't be removed");
    expect(within(dialog).getByRole("button", { name: "Close" })).toBeInTheDocument();
  });
});

describe("Opening an engagement", () => {
  it("goes to the next recommended screen and shows the guided path", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: KEYED }),
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({
        body: {
          ...READINESS,
          nav: { ...READINESS.nav, setup: "done", sources: "attention" },
          nav_counts: { sources: 2 },
          next_step: "sources",
        },
      }),
      "GET /api/engagements/e1/sources": () => ({ body: [] }),
    });
    renderApp("/engagements/e1");
    expect(await screen.findByRole("heading", { level: 1, name: "Sources" })).toBeInTheDocument();
    const nav = await screen.findByRole("navigation", { name: "Engagement steps" });
    expect(within(nav).getByRole("link", { name: "Setup, done" })).toHaveAttribute("href", "/engagements/e1/setup");
    expect(
      within(nav).getByRole("link", { name: "Sources, needs attention, 2 to resolve, recommended next step" }),
    ).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Gap analysis, not started, optional" })).toBeInTheDocument();
    expect(screen.getByRole("banner")).toHaveTextContent("Load control");
  });

  it("says plainly when the engagement no longer exists", async () => {
    fakeApi({ "GET /api/settings": () => ({ body: KEYED }) });
    renderApp("/engagements/gone");
    expect(await screen.findByRole("heading", { name: "Engagement not found" })).toBeInTheDocument();
    expect(screen.getByText(/It may have been deleted/)).toBeInTheDocument();
  });

  it("screens from later phases say when they arrive", async () => {
    fakeApi({
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    });
    renderApp("/engagements/e1/draft");
    expect(await screen.findByText(/The Draft screen arrives in build phase P3/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Setup" })).toHaveAttribute("href", "/engagements/e1/setup");
  });

  it("unknown engagement screens are not found", async () => {
    fakeApi({ "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }) });
    renderApp("/engagements/e1/nowhere");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
