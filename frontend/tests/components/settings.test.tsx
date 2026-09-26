import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { API_KEY_MESSAGE, OWNER_NAME_MESSAGE } from "../../src/lib/validation";
import { seriousViolations } from "../axe";
import { SETTINGS, fakeApi, renderApp, type Handler } from "../renderApp";

const KEY = "sk-" + "ant-" + "api03-" + "Pr1v4te".repeat(6) + "Zq9x";

const MODELS = {
  models: [
    { id: "claude-opus-5-5", display_name: "Claude Opus 5.5", pdf_input: true, structured_outputs: true,
      effort_levels: ["low", "medium", "high", "xhigh", "max"] },
    { id: "claude-lite-1", display_name: "Claude Lite 1", pdf_input: true, structured_outputs: true,
      effort_levels: ["low", "medium"] },
  ],
  from_anthropic: true,
  message: "",
};

function backend(overrides: Record<string, Handler> = {}) {
  let settings = { ...SETTINGS };
  return fakeApi({
    "GET /api/settings": () => ({ body: settings }),
    "GET /api/settings/models": () => ({ body: MODELS }),
    "GET /api/health": () => ({ body: { status: "ok", app_version: "0.1.0", prd_version: "1.5" } }),
    "PUT /api/settings/profile": (body) => {
      settings = { ...settings, owner_name: (body as { owner_name: string }).owner_name };
      return { body: settings };
    },
    "PUT /api/settings/key": () => {
      settings = { ...settings, key_set: true, key_last4: "Zq9x" };
      return { body: settings };
    },
    "PUT /api/settings/model": (body) => {
      const b = body as { model: string; effort: string; verifier_enabled: boolean };
      settings = { ...settings, model: b.model, effort: b.effort, verifier_enabled: b.verifier_enabled };
      return { body: settings };
    },
    ...overrides,
  });
}

async function openSettings() {
  renderApp("/settings");
  // Wait for the loaded cards, not the loading placeholders (which share the card titles).
  await screen.findByText(/No key saved yet\.|Saved key/);
}

afterEach(() => vi.unstubAllGlobals());

describe("Settings: your name", () => {
  it("saves a valid name and confirms with a toast", async () => {
    const { calls } = backend();
    await openSettings();
    const card = screen.getByRole("region", { name: "Your name" });
    const input = within(card).getByLabelText("Your name");
    fireEvent.change(input, { target: { value: "  Eric Yim " } });
    fireEvent.click(within(card).getByRole("button", { name: "Save name" }));
    expect(await screen.findByText("Your name was saved.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PUT /api/settings/profile")?.body).toEqual({ owner_name: "Eric Yim" });
    expect(input).toHaveValue("Eric Yim");
  });

  it("refuses an empty name before sending anything, with the message under the field", async () => {
    const { calls } = backend();
    await openSettings();
    const card = screen.getByRole("region", { name: "Your name" });
    const input = within(card).getByLabelText("Your name");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.click(within(card).getByRole("button", { name: "Save name" }));
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(OWNER_NAME_MESSAGE);
    expect(calls.some((c) => c.key === "PUT /api/settings/profile")).toBe(false);
  });

  it("shows the server's message if saving fails", async () => {
    backend({
      "PUT /api/settings/profile": () => ({
        status: 500,
        body: { error: { code: "IO", message: "Your settings couldn't be saved.", details: {} } },
      }),
    });
    await openSettings();
    const card = screen.getByRole("region", { name: "Your name" });
    fireEvent.click(within(card).getByRole("button", { name: "Save name" }));
    expect(await within(card).findByText("Your settings couldn't be saved.")).toBeInTheDocument();
  });
});

describe("Settings: Claude connection", () => {
  it("saves the key, clears the field and shows only the last 4 characters", async () => {
    const { calls } = backend();
    await openSettings();
    const card = screen.getByRole("region", { name: "Claude connection" });
    expect(card).toHaveTextContent("No key saved yet.");
    const input = within(card).getByLabelText("Claude API key");
    expect(input).toHaveAttribute("type", "password");
    fireEvent.change(input, { target: { value: KEY } });
    fireEvent.click(within(card).getByRole("button", { name: "Save key" }));
    expect(await screen.findByText(/Your API key was saved/)).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PUT /api/settings/key")?.body).toEqual({ anthropic_api_key: KEY });
    await waitFor(() => expect(card).toHaveTextContent("ending in Zq9x"));
    expect(within(card).getByLabelText("Replace the API key")).toHaveValue("");
    expect(document.body.innerHTML).not.toContain(KEY);
    expect(document.body.innerHTML).not.toContain(KEY.slice(0, 20));
  });

  it("refuses something that isn't a key before sending it", async () => {
    const { calls } = backend();
    await openSettings();
    const card = screen.getByRole("region", { name: "Claude connection" });
    fireEvent.change(within(card).getByLabelText("Claude API key"), { target: { value: "hello" } });
    fireEvent.click(within(card).getByRole("button", { name: "Save key" }));
    expect(within(card).getByText(API_KEY_MESSAGE)).toBeInTheDocument();
    expect(calls.some((c) => c.key === "PUT /api/settings/key")).toBe(false);
  });

  it("lists pass and fail for each check after Test connection", async () => {
    backend({
      "POST /api/settings/test-connection": () => ({
        body: {
          key_valid: true,
          model_available: true,
          capabilities: { pdf_input: true, structured_outputs: false },
          message: "Connected. Your key works and claude-opus-5-5 is available.",
        },
      }),
    });
    await openSettings();
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    const results = await screen.findByRole("group", { name: "Connection test results" });
    expect(results).toHaveTextContent("Connected. Your key works");
    const row = (label: string) => within(results).getByText(label).closest("li") as HTMLElement;
    expect(row("Key valid")).toHaveTextContent("Pass");
    expect(row("Model available")).toHaveTextContent("Pass");
    expect(row("PDF input")).toHaveTextContent("Yes");
    expect(row("Structured outputs")).toHaveTextContent("No");
  });

  it("shows the rejected-key message and marks later checks as not checked", async () => {
    backend({
      "POST /api/settings/test-connection": () => ({
        body: {
          key_valid: false,
          model_available: false,
          capabilities: { pdf_input: false, structured_outputs: false },
          message: "Your API key was rejected. Copy it again from the Claude Console and paste it here.",
        },
      }),
    });
    await openSettings();
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    const results = await screen.findByRole("group", { name: "Connection test results" });
    expect(results).toHaveTextContent("Your API key was rejected");
    expect(within(results).getByText("Key valid").closest("li")).toHaveTextContent("Fail");
    expect(within(results).getAllByText("Not checked")).toHaveLength(3);
  });

  it("shows an error with Copy details when Anthropic is busy", async () => {
    backend({
      "POST /api/settings/test-connection": () => ({
        status: 503,
        body: {
          error: {
            code: "AI_RATE_LIMIT",
            message: "Anthropic is busy right now, so the check couldn't finish. Try again in a minute.",
            details: { request_id: "abc123" },
          },
        },
      }),
    });
    await openSettings();
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Try again in a minute");
    expect(within(alert).getByRole("button", { name: "Copy details" })).toBeInTheDocument();
  });
});

describe("Settings: model", () => {
  it("offers only the effort levels the chosen model supports and saves the choice", async () => {
    const { calls } = backend();
    await openSettings();
    const card = screen.getByRole("region", { name: "Model" });
    const model = await within(card).findByLabelText("Model");
    const effort = within(card).getByLabelText("Effort");
    expect(within(effort).getAllByRole("option")).toHaveLength(5);
    fireEvent.change(model, { target: { value: "claude-lite-1" } });
    expect(within(effort).getAllByRole("option").map((o) => o.textContent)).toEqual(["Low", "Medium"]);
    expect(effort).toHaveValue("medium");
    fireEvent.click(within(card).getByRole("checkbox", { name: "Independent verifier" }));
    expect(within(card).getByText(/The verifier is off/)).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: "Save model settings" }));
    expect(await screen.findByText("Model settings saved.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PUT /api/settings/model")?.body).toEqual({
      model: "claude-lite-1",
      effort: "medium",
      verifier_enabled: false,
    });
  });

  it("explains when the list isn't from Anthropic yet", async () => {
    backend({
      "GET /api/settings/models": () => ({
        body: { ...MODELS, models: MODELS.models.slice(0, 1), from_anthropic: false,
                message: "Add your Claude API key to see every model available to you." },
      }),
    });
    await openSettings();
    expect(await screen.findByText(/Add your Claude API key to see every model/)).toBeInTheDocument();
  });
});

describe("Settings: page states", () => {
  it("shows the versions in About", async () => {
    backend();
    await openSettings();
    const about = screen.getByRole("region", { name: "About" });
    await waitFor(() => expect(about).toHaveTextContent("0.1.0"));
    expect(about).toHaveTextContent("1.5");
  });

  it("shows a plain error when settings can't load", async () => {
    backend({
      "GET /api/settings": () => ({
        status: 500,
        body: { error: { code: "IO", message: "Your settings couldn't be read.", details: {} } },
      }),
    });
    renderApp("/settings");
    expect(await screen.findByRole("alert")).toHaveTextContent("Your settings couldn't be loaded");
  });

  it("has no serious or critical accessibility violations, with results shown", async () => {
    backend({
      "POST /api/settings/test-connection": () => ({
        body: { key_valid: true, model_available: true,
                capabilities: { pdf_input: true, structured_outputs: true }, message: "Connected." },
      }),
    });
    const { container } = renderApp("/settings");
    await screen.findByText(/No key saved yet\./);
    await screen.findByLabelText("Effort");
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await screen.findByRole("group", { name: "Connection test results" });
    expect(await seriousViolations(container)).toEqual([]);
  });
});
