import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { seriousViolations } from "../axe";
import { SETTINGS, fakeApi, renderApp } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

describe("Home (Engagements) with the first-run checklist", () => {
  it("asks for the API key first, linking to Settings", async () => {
    fakeApi({ "GET /api/settings": () => ({ body: SETTINGS }) });
    renderApp("/");
    expect(screen.getByRole("heading", { level: 1, name: "Engagements" })).toBeInTheDocument();
    await screen.findByText(/0 of 3 steps done/);
    const checklist = screen.getByRole("region", { name: "Get started" });
    const link = within(checklist).getByRole("link", { name: "Add your Claude API key" });
    expect(link).toHaveAttribute("href", "/settings");
    expect(within(checklist).getAllByText("To do")).toHaveLength(3);
  });

  it("ticks the key step once a key is saved, showing only its last 4 characters", async () => {
    fakeApi({ "GET /api/settings": () => ({ body: { ...SETTINGS, key_set: true, key_last4: "Zq9x" } }) });
    renderApp("/");
    await screen.findByText(/1 of 3 steps done/);
    const checklist = screen.getByRole("region", { name: "Get started" });
    expect(checklist).toHaveTextContent("Key saved (ending Zq9x)");
    expect(within(checklist).getByText("Done")).toBeInTheDocument();
  });

  it("explains New engagement instead of disabling it", async () => {
    fakeApi({ "GET /api/settings": () => ({ body: SETTINGS }) });
    renderApp("/");
    fireEvent.click(screen.getAllByRole("button", { name: "New engagement" })[0] as HTMLElement);
    expect(await screen.findByText(/arrives in the next build phase \(P1\)/)).toBeInTheDocument();
  });

  it("shows a plain error with Copy details when settings can't load", async () => {
    fakeApi({
      "GET /api/settings": () => ({
        status: 500,
        body: { error: { code: "IO", message: "Your settings couldn't be read.", details: { request_id: "r9" } } },
      }),
    });
    renderApp("/");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Your settings couldn't be loaded");
    expect(alert).toHaveTextContent("Your settings couldn't be read.");
    expect(within(alert).getByRole("button", { name: "Copy details" })).toBeInTheDocument();
    expect(within(alert).getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows skeletons while loading", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));
    renderApp("/");
    expect(document.querySelector("[aria-busy='true']")).not.toBeNull();
  });

  it("has no serious or critical accessibility violations", async () => {
    fakeApi({ "GET /api/settings": () => ({ body: SETTINGS }) });
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
