import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AssumptionsForm, RoleCostsForm, ValueRegister } from "../../src/components/registers";
import type { Assumption, DispositionRow, RoleCosts, ValueReport } from "../../src/lib/value";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp } from "../renderApp";

// R10c (PRD §3.14-3.15, §5.4 Registers; criteria 90-91, constraint 9): the Disposition and value
// register, on the shapes the backend really sends (backend/tests/unit/test_acceptance_p10b.py).

const SYSTEM = JSON.parse(readFileSync(join(__dirname, "..", "fixtures", "system_records.json"), "utf-8")) as {
  dispositions: DispositionRow[];
  value: ValueReport;
  role_costs: RoleCosts;
  value_assumptions: Assumption[];
};
const VALUE = SYSTEM.value;
const ROWS = SYSTEM.dispositions;

afterEach(() => vi.unstubAllGlobals());

describe("Disposition and value register (R10c)", () => {
  it("keeps facts, interpretation and recommendation apart, each figure with its label", async () => {
    const onGoTo = vi.fn();
    const { container } = render(<ValueRegister report={VALUE} dispositions={ROWS} onGoTo={onGoTo} />);
    // Totals say when the cost is partial instead of showing it as the whole.
    expect(screen.getByText("103.9 h a month and SGD 2,865.60 a month (mixed), from 6 steps.")).toBeInTheDocument();
    expect(screen.getByText(/The cost is partial: 2 of the steps counted have no hourly cost/)).toBeInTheDocument();
    const phases = screen.getByRole("table", { name: "By phase" });
    expect(within(phases).getByRole("row", { name: /Check and load/ })).toHaveTextContent(
      "Check and load55 h a monthSGD 518.40 a month partial: 2 without a costmixed3 (2 without figures)",
    );

    const facts = screen.getByRole("table", { name: "Steps with measured time and volume" });
    const measured = VALUE.steps.filter((s) => s.evidence === "measured").map((s) => s.label);
    expect(within(facts).getAllByRole("rowheader").map((th) => within(th).getByRole("button").textContent)).toEqual(measured);
    expect(within(facts).getByRole("row", { name: /Draft load plan/ })).toHaveTextContent(
      "19.9 min measured108.3 a month measured35.9 h a monthSGD 1,723.20 a month",
    );
    expect(within(facts).getByRole("row", { name: /Load and return LIR/ })).toHaveTextContent("No hourly cost");

    const interpretation = screen.getByRole("table", { name: "Steps with estimated or assumed figures" });
    expect(within(interpretation).getByRole("row", { name: /Resolve or offload/ })).toHaveTextContent(
      "40 min estimated30 a month assumed20 h a monthNo hourly cost",
    );
    expect(within(interpretation).queryByRole("row", { name: /Draft load plan/ })).toBeNull();

    const without = screen.getByRole("list", { name: "Steps without figures" });
    expect(within(without).getByText("Busy wave?").closest("li")).toHaveTextContent(
      "Busy wave?: No time per case: none measured, none stated, no override. No volume per month: none measured, no override.",
    );

    // Recommendation: scenarios always "Potential, not committed"; a disposition no step has is left out.
    expect(screen.getByText("Potential, not committed.")).toBeInTheDocument();
    const scenarios = screen.getByRole("table", { name: "By disposition (potential, not committed)" });
    expect(within(scenarios).getAllByRole("rowheader").map((th) => th.textContent)).toEqual([
      "Automate (rules)",
      "AI-assisted",
      "Human approves",
      "Keep human",
    ]);
    expect(within(scenarios).getByRole("row", { name: /AI-assisted/ })).toHaveTextContent(
      "AI-assisted135.9 h a month50%17.9 h a month · SGD 861.60 a month",
    );
    const byStep = screen.getByRole("list", { name: "Disposition by step" });
    const card = within(byStep).getByText("Draft load plan").closest("li") as HTMLElement;
    expect(card).toHaveTextContent("· AI-assisted (suggested)");
    expect(card).toHaveTextContent(`Suggested: AI-assisted. ${ROWS[0]?.reason}`);
    // Only the view's steps: "Approve load plan" is not in the As done figures.
    expect(within(byStep).queryByText("Approve load plan")).toBeNull();
    expect(container).not.toHaveTextContent(/per person:|each person|by person/i);

    fireEvent.click(within(card).getByRole("button", { name: "Go to Draft load plan" }));
    expect(onGoTo).toHaveBeenCalledWith(ROWS[0]?.element_id);
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("shows Eric's own choice as his, with his note", () => {
    const rows = ROWS.map((r) => (r.label === "Draft load plan" ? { ...r, disposition: "keep_human" as const, note: "Needs expert eyes" } : r));
    render(<ValueRegister report={VALUE} dispositions={rows} onGoTo={vi.fn()} />);
    const card = screen.getByText("Draft load plan", { selector: "p" }).closest("li") as HTMLElement;
    expect(card).toHaveTextContent("· Keep human (your choice)");
    expect(card).toHaveTextContent("Your note: Needs expert eyes");
  });

  it("explains an empty view instead of showing empty tables", () => {
    render(<ValueRegister report={{ ...VALUE, steps: [], phases: [], scenarios: [] }} dispositions={ROWS} onGoTo={vi.fn()} />);
    expect(screen.getByText(/No steps in this view yet/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("role costs: saves each role's cost, empty as none, and refuses a figure that isn't a cost", async () => {
    const onSave = vi.fn();
    const { container } = render(<RoleCostsForm costs={SYSTEM.role_costs} busy={false} error={null} onSave={onSave} />);
    const lead = screen.getByRole("group", { name: "Load control lead" });
    fireEvent.change(within(lead).getByLabelText("Hourly cost (SGD)"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Save role costs" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Give an hourly cost from 0 to 100,000.");
    expect(onSave).not.toHaveBeenCalled();
    fireEvent.change(within(lead).getByLabelText("Hourly cost (SGD)"), { target: { value: "62.5" } });
    fireEvent.change(within(lead).getByLabelText("Note (optional)"), { target: { value: " Payroll average " } });
    fireEvent.click(screen.getByRole("button", { name: "Save role costs" }));
    expect(onSave).toHaveBeenCalledWith([
      { role_id: "id-3", hourly_cost: 48, note: "Loaded rate" },
      { role_id: "id-16", hourly_cost: 62.5, note: "Payroll average" },
      { role_id: "id-17", hourly_cost: null, note: "" },
      { role_id: "id-18", hourly_cost: null, note: "" },
      { role_id: "id-19", hourly_cost: null, note: "" },
    ]);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("assumptions: each disposition's reduction, marked default, from 0 to 100 percent", async () => {
    const onSave = vi.fn();
    const { container } = render(
      <AssumptionsForm assumptions={SYSTEM.value_assumptions} busy={false} error="The server said no." onSave={onSave} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("The server said no.");
    const ai = screen.getByRole("group", { name: "AI-assisted (default)" });
    fireEvent.change(within(ai).getByLabelText("Reduction (%)"), { target: { value: "120" } });
    fireEvent.click(screen.getByRole("button", { name: "Save assumptions" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Give a reduction from 0 to 100 percent.");
    expect(onSave).not.toHaveBeenCalled();
    fireEvent.change(within(ai).getByLabelText("Reduction (%)"), { target: { value: "40" } });
    fireEvent.change(within(ai).getByLabelText("Note (optional)"), { target: { value: "Pilot result" } });
    fireEvent.click(screen.getByRole("button", { name: "Save assumptions" }));
    expect(onSave).toHaveBeenCalledWith([
      { disposition: "delete", reduction_pct: 100, note: "" },
      { disposition: "automate_rules", reduction_pct: 80, note: "" },
      { disposition: "ai_assisted", reduction_pct: 40, note: "Pilot result" },
      { disposition: "human_approves", reduction_pct: 30, note: "" },
      { disposition: "keep_human", reduction_pct: 0, note: "" },
    ]);
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("Registers screen with the value calculator (R10c)", () => {
  const DRAFT = {
    id: "v2", engagement_id: "e1", label: "v0.1", state: "draft", created_at: "2026-09-28T09:00:00+00:00",
    published_at: null, published_by: null, parent_version_id: null,
  }; // prettier-ignore
  const REGISTERS = {
    k_risk: [], ai_flags: [], constraints_by_cause: [], external_practice: [], questions: [],
    rejected_claims: { items: [], total: 0, scrub_count: 0, instruction_like_count: 0 },
  }; // prettier-ignore

  function backend(on: boolean) {
    const valueUrls: string[] = [];
    const api = fakeApi({
      "GET /api/settings": () => ({ body: { ...SETTINGS, value_enabled: on } }),
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/versions": () => ({ body: [DRAFT] }),
      "GET /api/versions/v2/registers": () => ({ body: REGISTERS }),
      "GET /api/versions/v2/value": (_body, url) => {
        valueUrls.push(url ?? "");
        return { body: url?.endsWith("view=documented") ? { ...VALUE, view: "documented", steps: [], phases: [], scenarios: [] } : VALUE };
      },
      "GET /api/versions/v2/dispositions": () => ({ body: ROWS }),
      "GET /api/engagements/e1/role-costs": () => ({ body: SYSTEM.role_costs }),
      "PUT /api/engagements/e1/role-costs": () => ({ body: SYSTEM.role_costs }),
      "GET /api/engagements/e1/value-assumptions": () => ({ body: SYSTEM.value_assumptions }),
      "PUT /api/engagements/e1/value-assumptions": () => ({
        status: 422,
        body: { error: { code: "VALIDATION", message: "Give a reduction from 0 to 100 percent.", details: { field: "reduction_pct" } } },
      }),
    });
    return { ...api, valueUrls };
  }

  it("while off: the register isn't offered, its address falls back to K-RISK, and nothing is asked for", async () => {
    const { calls } = backend(false);
    renderApp("/engagements/e1/registers?register=value");
    const choice = await screen.findByRole("radiogroup", { name: "Register" });
    await waitFor(() => expect(calls.some((c) => c.key === "GET /api/settings")).toBe(true));
    expect(within(choice).queryByRole("radio", { name: "Disposition and value" })).toBeNull();
    expect(within(choice).getByRole("radio", { name: "K-RISK" })).toBeChecked();
    expect(calls.some((c) => /\/value|\/dispositions|role-costs|value-assumptions/.test(c.key))).toBe(false);
  });

  it("while on: shows the figures, switches view, and saves role costs and assumptions", async () => {
    const { calls, valueUrls } = backend(true);
    const { container } = renderApp("/engagements/e1/registers?register=value");
    const panel = await screen.findByRole("region", { name: "Disposition and value" });
    expect(await within(panel).findByText("103.9 h a month and SGD 2,865.60 a month (mixed), from 6 steps.")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);

    fireEvent.click(within(panel).getByRole("button", { name: "Save role costs" }));
    expect(await screen.findByText("Role costs saved.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PUT /api/engagements/e1/role-costs")?.body).toEqual({
      rows: SYSTEM.role_costs.rows.map((r) => ({ role_id: r.role_id, hourly_cost: r.hourly_cost, note: r.note })),
    });

    fireEvent.click(within(panel).getByRole("button", { name: "Save assumptions" }));
    expect(await within(panel).findByRole("alert")).toHaveTextContent("Give a reduction from 0 to 100 percent.");

    fireEvent.click(within(panel).getByRole("radio", { name: "As documented" }));
    expect(await within(panel).findByText(/No steps in this view yet/)).toBeInTheDocument();
    expect(valueUrls.map((u) => u.split("?")[1])).toEqual(expect.arrayContaining(["view=done", "view=documented"]));
  });
});
