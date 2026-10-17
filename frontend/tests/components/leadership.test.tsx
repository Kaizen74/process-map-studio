import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StepsBehind } from "../../src/components/leadership";
import type { LeadershipView } from "../../src/lib/leadership";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

const PUBLISHED = {
  id: "v1",
  engagement_id: "e1",
  label: "v1.0",
  state: "published",
  created_at: "2026-09-28T09:00:00+00:00",
  published_at: "2026-09-28T10:00:00+00:00",
  published_by: "Owner",
  parent_version_id: null,
};

const links = { work: [], wait: [], rework_loops: [], handoffs: [], divergence: {} };
const VIEW: LeadershipView = {
  version: { id: "v1", label: "v1.0", state: "published" },
  facts: {
    phases: [
      { phase_id: "p1", name: "Plan", work_min: 20, wait_min: 0, rework_loops: 1, handoffs: 3, divergence_counts: {},
        links: { ...links, work: ["plan"], rework_loops: ["approve"], handoffs: ["plan", "approve"] } },
      { phase_id: "p2", name: "Check and load", work_min: 80, wait_min: 15, rework_loops: 1, handoffs: 4,
        divergence_counts: { threshold: 1 },
        links: { ...links, work: ["lir"], wait: ["lir"], divergence: { threshold: ["lir"] } } },
    ],
    sources: 5,
  }, // prettier-ignore
  interpretation: {
    causes: [
      { cause_type: "system_fragmentation", systemic: true, reason: "On 2 steps in 2 lanes: Load controller, Ramp.",
        phases: [{ phase_id: "p2", name: "Check and load" }], lanes: ["Load controller", "Ramp"],
        evidence_weight: { supporting: 3, sources: 5 }, confidence: 0.72,
        constraints: [{ element_id: "lir", label: "Load and return LIR", text: "The loading report is on paper and re-keyed", is_key: true }],
        element_ids: ["special", "lir"] },
      { cause_type: "single_point_knowledge", systemic: false, reason: "On 1 step in one lane (Load controller).",
        phases: [{ phase_id: "p1", name: "Plan" }], lanes: ["Load controller"],
        evidence_weight: { supporting: 3, sources: 5 }, confidence: 0.85,
        constraints: [{ element_id: "plan", label: "Draft load plan", text: "Widebody plans rely on two controllers", is_key: false }],
        element_ids: ["plan"] },
    ],
  }, // prettier-ignore
  recommendation: {
    recoverable_wait_min: 15,
    recoverable_wait_element_ids: ["lir"],
    rework_loops: 3,
    rework_element_ids: ["approve"],
    ai_flags: [
      { element_id: "special", label: "Special loads OK?", lane: "Load controller", mechanism: "rule_based",
        component: "reasoning", input: "Special load notification", output: "Accept or refuse each special load",
        handoff: "Load controller", basis: "rule_based_automate_candidate" },
    ], // prettier-ignore
    decisions_needed: [{ cause_type: "system_fragmentation", text: "" }],
  },
  reality: null,
};
const GRAPH = {
  elements: [
    { id: "plan", label: "Draft load plan" },
    { id: "approve", label: "Approve load plan" },
    { id: "special", label: "Special loads OK?" },
    { id: "lir", label: "Load and return LIR" },
  ],
};

function backend(versions: unknown[] = [PUBLISHED]) {
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/versions": () => ({ body: versions }),
    "GET /api/versions/v1/leadership": () => ({ body: VIEW }),
    "GET /api/versions/v1/graph": () => ({ body: GRAPH }),
    "PUT /api/versions/v1/leadership/decisions": (body) => ({ body }),
  });
}

describe("a figure and the steps behind it", () => {
  it("lists the steps and opens each one; a figure with no steps is plain text", () => {
    const onOpen = vi.fn();
    const labels = new Map([["lir", "Load and return LIR"]]);
    const { rerender } = render(<StepsBehind figure="Wait 15 min" ids={["lir"]} labels={labels} onOpen={onOpen} />);
    fireEvent.click(screen.getByText("Wait 15 min"));
    fireEvent.click(screen.getByRole("button", { name: "Open Load and return LIR" }));
    expect(onOpen).toHaveBeenCalledWith("lir");
    expect(screen.getByText(/1 step/)).toBeInTheDocument();
    rerender(<StepsBehind figure="Wait 0 min" ids={[]} labels={labels} onOpen={onOpen} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("Wait 0 min")).toBeInTheDocument();
  });
});

describe("Leadership screen (PRD §5.4)", () => {
  it("without a published version, explains why and links to Review", async () => {
    backend([{ ...PUBLISHED, state: "draft", published_at: null }]);
    const { container } = renderApp("/engagements/e1/leadership");
    expect(await screen.findByText(/Publish a version first/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Review" })).toHaveAttribute("href", "/engagements/e1/review");
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("shows Facts, Interpretation and Recommendation apart, each figure with its steps", async () => {
    backend();
    const { container } = renderApp("/engagements/e1/leadership");
    const facts = await screen.findByRole("region", { name: "Facts" });
    const interpretation = screen.getByRole("region", { name: "Interpretation" });
    const recommendation = screen.getByRole("region", { name: "Recommendation" });
    expect(within(facts).getByText("Plan")).toBeInTheDocument();
    expect(within(facts).getByText("Wait 15 min")).toBeInTheDocument();
    expect(within(facts).getByText("3 handoffs between lanes")).toBeInTheDocument();
    expect(within(facts).getByText("Threshold disagreement: 1")).toBeInTheDocument();
    expect(within(facts).getAllByText("No disagreement between sources")).toHaveLength(1);
    expect(within(interpretation).getByText("Systemic")).toBeInTheDocument();
    expect(within(interpretation).getByText("Local")).toBeInTheDocument();
    expect(interpretation).toHaveTextContent("Supported by 3 of 5 sources · Confidence 72%");
    expect(interpretation).toHaveTextContent("The loading report is on paper and re-keyed (key constraint)");
    expect(within(recommendation).getByText("Recoverable wait: 15 min")).toBeInTheDocument();
    expect(within(recommendation).getByText("Rule-based: an automation candidate")).toBeInTheDocument();
    // Recommendation-type content stays out of Facts (constraint 9).
    expect(facts).not.toHaveTextContent("Decision needed");
    expect(await seriousViolations(container)).toEqual([]);
    // Every figure opens its steps.
    await waitFor(() => expect(within(facts).getByText("Work 80 min")).toBeInTheDocument());
    const work = within(facts).getByText("Work 80 min").closest("details");
    if (!work) throw new Error("the figure is a disclosure");
    expect(work.open).toBe(false);
    fireEvent.click(within(facts).getByText("Work 80 min"));
    expect(within(work).getByRole("button", { name: "Open Load and return LIR" })).toBeInTheDocument();
  });

  it("saves a decision line per systemic cause", async () => {
    const { calls } = backend();
    renderApp("/engagements/e1/leadership");
    const field = await screen.findByRole("textbox", { name: "Decision needed: System fragmentation" });
    expect(screen.queryByRole("textbox", { name: /Single point knowledge/i })).toBeNull();
    fireEvent.change(field, { target: { value: "  Fund one digital loading report  " } });
    fireEvent.click(screen.getByRole("button", { name: "Save decisions" }));
    await waitFor(() =>
      expect(calls.find((c) => c.key === "PUT /api/versions/v1/leadership/decisions")?.body).toEqual([
        { cause_type: "system_fragmentation", text: "Fund one digital loading report" },
      ]),
    );
    expect(await screen.findByText("Decisions saved.")).toBeInTheDocument();
    fireEvent.change(field, { target: { value: "x".repeat(501) } });
    fireEvent.click(screen.getByRole("button", { name: "Save decisions" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Keep each decision under 500 characters.");
  });
});
