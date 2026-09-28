import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AiFlagList, CauseList, ConstraintGroups, ExternalPracticeList, KRiskList } from "../../src/components/registers";
import type { CauseEntry, Registers } from "../../src/lib/registers";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

const REGISTERS: Registers = {
  k_risk: [
    {
      element_id: "plan",
      label: "Draft load plan",
      lane: "Load controller",
      k_risk: "Widebody plans rely on the Load controller and one other controller",
    },
  ],
  ai_flags: [
    {
      element_id: "special",
      label: "Special loads OK?",
      lane: "Load controller",
      mechanism: "rule_based",
      component: "reasoning",
      input: "Special load notification",
      output: "Accept or refuse each special load",
      handoff: "Load controller",
      basis: "rule_based_automate_candidate",
    },
  ],
  constraints_by_cause: [
    {
      cause_type: "system_fragmentation",
      constraints: [
        { element_id: "lir", label: "Load and return LIR", text: "The loading report is on paper and re-keyed", is_key: true, provenance: "O" },
      ],
    },
    {
      cause_type: null,
      constraints: [{ element_id: "issue", label: "Issue load sheet", text: "Printer jams", is_key: false, provenance: "O" }],
    },
  ],
  external_practice: [],
  questions: [
    {
      id: "q1",
      element_id: "plan",
      element_label: "Draft load plan",
      phase_id: "p1",
      phase_name: "Plan",
      question: "Who approves the load plan in practice?",
      reason: "documented_only",
      status: "open",
    },
  ],
  rejected_claims: { items: [], total: 0, scrub_count: 0, instruction_like_count: 0 },
};

const CAUSES: CauseEntry[] = [
  {
    id: "c1",
    element_stable_key: "load-and-return-lir",
    element_id: "lir",
    element_label: "Load and return LIR",
    divergence_type: "threshold",
    pattern: "Threshold divergence: 10 min in the SOP vs up to 15 min wait in practice.",
    inferred_cause: "The loading report is on paper and re-keyed",
    cause_type: "system_fragmentation",
    provenance: "I",
    validation_result: "pending",
    created_at: "2026-09-28T09:00:00+00:00",
  },
  {
    id: "c2",
    element_stable_key: "deviation-in-limits",
    element_id: null,
    element_label: "Deviation in limits?",
    divergence_type: "ownership",
    pattern: "Ownership divergence: the Load control lead decides in the SOP, the Captain in practice.",
    inferred_cause: "",
    cause_type: null,
    provenance: "O",
    validation_result: "confirmed",
    created_at: "2026-09-28T09:00:01+00:00",
  },
];

describe("register lists", () => {
  it("each entry names its step and offers Go to; empty registers say what would appear", () => {
    const onGoTo = vi.fn();
    const { rerender } = render(<KRiskList items={REGISTERS.k_risk} onGoTo={onGoTo} />);
    expect(screen.getByText(/Widebody plans rely/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Go to Draft load plan" }));
    expect(onGoTo).toHaveBeenCalledWith("plan");
    rerender(<KRiskList items={[]} onGoTo={onGoTo} />);
    expect(screen.getByText(/No knowledge risks recorded/)).toBeInTheDocument();
    rerender(<ExternalPracticeList items={[]} onGoTo={onGoTo} />);
    expect(screen.getByText(/No recommended-practice steps/)).toBeInTheDocument();
    rerender(
      <ExternalPracticeList
        items={[{ element_id: "r", label: "Weigh bags", r_reference: "IATA AHM 510" }]}
        onGoTo={onGoTo}
      />,
    );
    expect(screen.getByText("IATA AHM 510")).toBeInTheDocument();
  });

  it("an AI flag shows the five fields; a judgment step's flag is support only", () => {
    const [flag] = REGISTERS.ai_flags;
    if (!flag) throw new Error("flag");
    const { rerender } = render(<AiFlagList items={[flag]} onGoTo={vi.fn()} />);
    for (const term of ["Component", "Input", "Output", "Handoff", "Basis"]) {
      expect(screen.getByText(term).tagName).toBe("DT");
    }
    expect(screen.getByText("Rule-based: an automation candidate")).toBeInTheDocument();
    rerender(<AiFlagList items={[{ ...flag, mechanism: "judgment" }]} onGoTo={vi.fn()} />);
    expect(screen.getByText("Judgment: support only")).toBeInTheDocument();
  });

  it("constraints are grouped by cause, key ones marked in words too", async () => {
    const { container } = render(<ConstraintGroups groups={REGISTERS.constraints_by_cause} onGoTo={vi.fn()} />);
    const fragmentation = screen.getByRole("region", { name: "System fragmentation" });
    expect(within(fragmentation).getByText("Key constraint:", { exact: false })).toHaveClass("visually-hidden");
    expect(fragmentation).toHaveTextContent("Key · Provenance O");
    expect(screen.getByRole("region", { name: "No cause type recorded" })).toHaveTextContent("Printer jams");
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("a cause entry keeps fact and inference apart and offers Confirm, Refute or Reopen", async () => {
    const onValidate = vi.fn();
    const { container } = render(
      <CauseList entries={CAUSES} busyId={null} onGoTo={vi.fn()} onValidate={onValidate} />,
    );
    const [lir, deviation] = screen.getAllByRole("listitem").filter((li) => li.classList.contains("register-card"));
    if (!lir || !deviation) throw new Error("two entries");
    expect(lir).toHaveTextContent("What differs (observed): Threshold divergence");
    expect(lir).toHaveTextContent("Possible cause (inferred from this step's constraints, System fragmentation)");
    expect(within(lir).getByText("Pending")).toHaveClass("chip--dashed");
    fireEvent.click(within(lir).getByRole("button", { name: "Confirm" }));
    expect(onValidate).toHaveBeenCalledWith(CAUSES[0], "confirmed");
    fireEvent.click(within(lir).getByRole("button", { name: "Refute" }));
    expect(onValidate).toHaveBeenLastCalledWith(CAUSES[0], "refuted");
    expect(deviation).toHaveTextContent("Cause not known yet: ask your SME in the validation session.");
    expect(deviation).toHaveTextContent("This step is no longer on the map.");
    fireEvent.click(within(deviation).getByRole("button", { name: "Reopen" }));
    expect(onValidate).toHaveBeenLastCalledWith(CAUSES[1], "pending");
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("Registers screen (PRD §5.4)", () => {
  const DRAFT = {
    id: "v2",
    engagement_id: "e1",
    label: "v0.1",
    state: "draft",
    created_at: "2026-09-28T09:00:00+00:00",
    published_at: null,
    published_by: null,
    parent_version_id: null,
  };

  function backend(versions: unknown[] = [DRAFT]) {
    let causes = CAUSES;
    return fakeApi({
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/versions": () => ({ body: versions }),
      "GET /api/versions/v2/registers": () => ({ body: REGISTERS }),
      "GET /api/engagements/e1/cause-library": () => ({ body: causes }),
      "PATCH /api/cause-library/c1": (body) => {
        const result = (body as { validation_result: string }).validation_result;
        causes = causes.map((c) => (c.id === "c1" ? { ...c, validation_result: result } : c));
        return { body: causes[0] };
      },
    });
  }

  it("opens on K-RISK and switches register with the segmented control", async () => {
    backend();
    const { container } = renderApp("/engagements/e1/registers");
    expect(await screen.findByText(/Widebody plans rely/)).toBeInTheDocument();
    const choice = screen.getByRole("radiogroup", { name: "Register" });
    expect(within(choice).getAllByRole("radio").map((r) => r.textContent)).toEqual([
      "K-RISK",
      "AI flags",
      "Constraints by cause",
      "External practice (R)",
      "Validation questions",
      "Rejected claims",
      "Cause library",
    ]);
    expect(await seriousViolations(container)).toEqual([]);
    for (const [name, text] of [
      ["AI flags", "Accept or refuse each special load"],
      ["Constraints by cause", "The loading report is on paper and re-keyed"],
      ["External practice (R)", "No recommended-practice steps"],
      ["Validation questions", "Who approves the load plan in practice?"],
      ["Rejected claims", "No claims were rejected"],
    ] as const) {
      fireEvent.click(within(choice).getByRole("radio", { name }));
      expect(await screen.findByText(new RegExp(text.replace(/[?]/g, "\\?")))).toBeInTheDocument();
      expect(await seriousViolations(container)).toEqual([]);
    }
  });

  it("the cause library opens from the address, and Confirm saves with a message", async () => {
    const { calls } = backend();
    const { container } = renderApp("/engagements/e1/registers?register=causes");
    const lir = (await screen.findByText(/Threshold divergence/)).closest("li") as HTMLElement;
    fireEvent.click(within(lir).getByRole("button", { name: "Confirm" }));
    expect(await screen.findByText("Cause confirmed.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PATCH /api/cause-library/c1")?.body).toEqual({ validation_result: "confirmed" });
    expect(await within(lir).findByRole("button", { name: "Reopen" })).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("Go to opens the step on Review", async () => {
    backend();
    renderApp("/engagements/e1/registers");
    fireEvent.click(await screen.findByRole("button", { name: "Go to Draft load plan" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Review" })).toBeInTheDocument();
  });

  it("no draft yet: says so and links to Draft", async () => {
    backend([]);
    renderApp("/engagements/e1/registers");
    expect(await screen.findByText(/The registers fill up from the draft map/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Draft" })).toHaveAttribute("href", "/engagements/e1/draft");
  });
});
