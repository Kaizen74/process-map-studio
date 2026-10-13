import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DispositionValueSection } from "../../src/components/panel";
import { DISPOSITION_LABELS, money, type DispositionRow, type StepValue, type ValueReport } from "../../src/lib/value";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp } from "../renderApp";
import { SAMPLE, elementByLabel, graphFor, layoutFor } from "../sampleMap";

// R10b (PRD §5.7.7 4e, §3.14-3.15; criteria 90-91): the panel's Disposition and value section,
// on the shapes the backend really sends (backend/tests/unit/test_acceptance_p10b.py).

const SYSTEM = JSON.parse(readFileSync(join(__dirname, "..", "fixtures", "system_records.json"), "utf-8")) as {
  dispositions: DispositionRow[];
  value: ValueReport;
};
const idOf = (label: string) => elementByLabel(label).id;
const ROWS: DispositionRow[] = SYSTEM.dispositions.map((r) => ({ ...r, element_id: idOf(r.label) }));
const VALUE: ValueReport = { ...SYSTEM.value, steps: SYSTEM.value.steps.map((s) => ({ ...s, element_id: idOf(s.label) })) };
const row = (label: string) => ROWS.find((r) => r.label === label) as DispositionRow;
const value = (label: string) => VALUE.steps.find((s) => s.label === label) as StepValue;
const POTENTIAL = "Potential, not committed";

function edit() {
  return { busy: false, error: null, onChoose: vi.fn(), overrideError: null, onOverride: vi.fn() };
}

describe("Disposition and value section (R10b)", () => {
  it("shows the suggestion with its reason, the figures with their labels and the scenario as potential", async () => {
    const draft = value("Draft load plan");
    const { container } = render(
      <DispositionValueSection row={row("Draft load plan")} value={draft} currency="SGD" potential={POTENTIAL} />,
    );
    const section = screen.getByRole("region", { name: "Disposition and value" });
    expect(section).toHaveTextContent(`AI-assisted. ${row("Draft load plan").reason}`);
    expect(section).toHaveTextContent("Not chosen yet: the figures use the suggestion.");
    expect(section).toHaveTextContent("19.9 min a case · measured");
    expect(section).toHaveTextContent("108.3 cases a month · measured");
    expect(section).toHaveTextContent(`${money(draft.cost_per_month as number, "SGD")} a month · measured`);
    expect(section).toHaveTextContent(/If ai-assisted: up to 17\.9 h a month and SGD 861\.60 a month could be released \(50% assumed\)\. Potential, not committed\./);
    expect(screen.queryByRole("button")).toBeNull(); // read-only without edit
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("says what is missing instead of inventing a figure", () => {
    const missing = VALUE.steps.find((s) => s.missing.length > 0) as StepValue;
    render(<DispositionValueSection row={row(missing.label)} value={missing} currency="SGD" potential={POTENTIAL} />);
    for (const m of missing.missing) expect(screen.getByText(m)).toBeInTheDocument();
  });

  it("accepts the suggestion in one click when it is open to the step", () => {
    const actions = edit();
    const open = ROWS.find((r) => r.allowed.includes(r.suggested) && r.disposition === null) as DispositionRow;
    render(<DispositionValueSection row={open} currency="SGD" potential={POTENTIAL} edit={actions} />);
    fireEvent.click(screen.getByRole("button", { name: "Accept the suggestion" }));
    expect(actions.onChoose).toHaveBeenCalledWith({ disposition: open.suggested, note: "" });
  });

  it("offers only the allowed dispositions and explains each refused one", async () => {
    const actions = edit();
    const deviation = row("Deviation in limits?");
    const { container } = render(<DispositionValueSection row={deviation} currency="SGD" potential={POTENTIAL} edit={actions} />);
    fireEvent.click(screen.getByRole("button", { name: /Choose another|Change disposition/ }));
    const choices = screen.getByRole("group", { name: "Your disposition" });
    expect(within(choices).getAllByRole("radio").map((r) => (r as HTMLInputElement).value)).toEqual(deviation.allowed);
    const refused = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(refused).toEqual(deviation.not_allowed.map((n) => `${DISPOSITION_LABELS[n.disposition]}: ${n.reason}`));
    fireEvent.click(within(choices).getByRole("radio", { name: /Human approves/ }));
    fireEvent.change(screen.getByRole("combobox", { name: "Risk" }), { target: { value: "safety" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Note (optional)" }), { target: { value: " Captain signs " } });
    fireEvent.click(screen.getByRole("button", { name: "Save disposition" }));
    expect(actions.onChoose).toHaveBeenCalledWith({ disposition: "human_approves", note: "Captain signs", risk_flag: "safety" });
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("clears a chosen disposition, and shows the server's refusal in plain words", () => {
    const actions = { ...edit(), error: "Add a complete AI flag first: component, input, output, handoff and basis." };
    const chosen = { ...row("Issue load sheet"), disposition: "keep_human" as const, note: "Kept for now" };
    render(<DispositionValueSection row={chosen} currency="SGD" potential={POTENTIAL} edit={actions} />);
    expect(screen.getByRole("region", { name: "Disposition and value" })).toHaveTextContent("Keep human Kept for now");
    expect(screen.getByRole("alert")).toHaveTextContent("Add a complete AI flag first");
    fireEvent.click(screen.getByRole("button", { name: "Clear my choice" }));
    expect(actions.onChoose).toHaveBeenCalledWith({ disposition: null, note: "" });
  });

  it("asks where Eric's own figures come from before saving them", () => {
    const actions = edit();
    render(<DispositionValueSection row={row("Resolve or offload")} currency="SGD" potential={POTENTIAL} edit={actions} />);
    fireEvent.click(screen.getByRole("button", { name: "Set your own figures for this step" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Cases a month" }), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Save figures" }));
    expect(screen.getByText("Say where the figure comes from.")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Minutes of work a case" }), { target: { value: "-2" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Where the figures come from" }), { target: { value: "Shift log" } });
    fireEvent.click(screen.getByRole("button", { name: "Save figures" }));
    expect(screen.getByText("Give figures above 0, or leave them empty.")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Minutes of work a case" }), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save figures" }));
    expect(actions.onOverride).toHaveBeenCalledWith({ time_min: null, volume_month: 30, note: "Shift log" });
  });
});

describe("Review with the value calculator (R10b)", () => {
  const VID = SAMPLE.graph.version.id;
  beforeEach(() => window.localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  function backend(on: boolean) {
    return fakeApi({
      "GET /api/settings": () => ({ body: { ...SETTINGS, value_enabled: on } }),
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/draft": () => ({
        body: { job: null, version: { id: VID, engagement_id: "e1", label: "v0.1", state: "draft",
          created_at: "2026-09-27T10:00:00+00:00" }, summary: null }, // prettier-ignore
      }),
      [`GET /api/versions/${VID}/graph`]: (_body, url) => ({ body: graphFor(url) }),
      [`GET /api/versions/${VID}/layout`]: (_body, url) => ({ body: layoutFor(url) }),
      [`GET /api/versions/${VID}/dispositions`]: () => ({ body: ROWS }),
      [`GET /api/versions/${VID}/value`]: () => ({ body: VALUE }),
      [`PUT /api/elements/${idOf("Draft load plan")}/disposition`]: () => ({ body: { ...row("Draft load plan"), disposition: "keep_human" } }),
      ...Object.fromEntries(
        Object.entries(SAMPLE.elements).map(([id, element]) => [`GET /api/elements/${id}`, () => ({ body: element })]),
      ),
    });
  }

  it("while off: no section and nothing about dispositions or value is asked for", async () => {
    const { calls } = backend(false);
    renderApp(`/engagements/e1/review?step=${idOf("Draft load plan")}`);
    expect(await screen.findByRole("region", { name: "Evidence" })).toBeInTheDocument();
    await waitFor(() => expect(calls.some((c) => c.key === "GET /api/settings")).toBe(true));
    expect(screen.queryByRole("region", { name: "Disposition and value" })).toBeNull();
    expect(calls.some((c) => c.key.includes("/dispositions") || c.key.includes("/value"))).toBe(false);
  });

  it("while on: the selected step shows its section, and a choice is saved", async () => {
    const { calls } = backend(true);
    const { container } = renderApp(`/engagements/e1/review?step=${idOf("Draft load plan")}`);
    const section = await screen.findByRole("region", { name: "Disposition and value" });
    await waitFor(() => expect(section).toHaveTextContent("19.9 min a case · measured"));
    fireEvent.click(within(section).getByRole("button", { name: "Choose another" }));
    fireEvent.click(within(section).getByRole("radio", { name: /Keep human/ }));
    fireEvent.click(within(section).getByRole("button", { name: "Save disposition" }));
    await waitFor(() =>
      expect(calls.find((c) => c.key === `PUT /api/elements/${idOf("Draft load plan")}/disposition`)?.body).toEqual({
        disposition: "keep_human",
        note: "",
        risk_flag: "none",
      }),
    );
    expect(await seriousViolations(container)).toEqual([]);
  });
});
