import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SopRegister } from "../../src/api/types";
import { ProcessAtAGlance } from "../../src/components/leadership";
import { RaciMatrix } from "../../src/components/tabs/RaciMatrix";
import { handoffsFrom, raciCounts } from "../../src/lib/accountability";
import { deviationLine, type Comparison } from "../../src/lib/comparisons";
import type { LeadershipView, ProcessSummary } from "../../src/lib/leadership";
import type { Graph } from "../../src/lib/mapTypes";
import { sopCountsLine, uncitedLine } from "../../src/lib/sources";
import { seriousViolations } from "../axe";
import sample from "../fixtures/accountability_sample.json";

// The brief's acceptance tests (§3.20; DECISIONS 110) on the screens, read from the Belmar
// fixture exactly as the backend sends it (backend/tests/unit/test_acceptance_accountability.py
// writes accountability_sample.json): the backend and the frontend agree on every figure.

const GRAPH = sample.graph as unknown as Graph;
const REGISTER = sample.sop_register as SopRegister;
const LEADERSHIP = sample.leadership as unknown as LeadershipView;
const COMPARISON = sample.comparison as unknown as Comparison;
const byCode = (code: string) => GRAPH.elements.find((e) => e.code === code);

describe("the Belmar fixture on the screens", () => {
  it("test 4: the RACI matrix marks S-03, S-05 and S-07 and reads the count line", async () => {
    const { container } = render(
      <RaciMatrix graph={GRAPH} laneOrder={GRAPH.roles.map((r) => r.id)} selectedId={null} onSelect={vi.fn()} />,
    );
    expect(
      screen.getByText(
        "4 decisions · 2 decided by a different role from the documents · 3 where the one who decides is not accountable · 2 with a contested A",
      ),
    ).toBeInTheDocument();
    const marked = screen
      .getAllByText("decides ≠ accountable")
      .map((m) => m.closest("tr")?.querySelector("button")?.textContent);
    expect(marked.sort()).toEqual(
      ["S-03", "S-05", "S-07"].map((c) => byCode(c)?.label).sort(),
    );
    expect(raciCounts(GRAPH.elements, GRAPH.roles)).toEqual({ decisions: 4, paperDiffers: 2, split: 3, contested: 2 });
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("test 8: the Sources line, and the steps citing no SOP or manual (DECISIONS 113)", () => {
    expect(sopCountsLine(REGISTER.counts)).toBe(
      "2 SOPs · 1 without an owner · 1 with nobody to update them · 0 review overdue · 1 uncontrolled",
    );
    expect(uncitedLine(REGISTER.map as NonNullable<SopRegister["map"]>)).toBe(
      "On the current map (v1.0): 2 of 11 steps cite no SOP or manual.",
    );
  });

  it("tests 9 and 12: the two leadership lines", () => {
    const summary = LEADERSHIP.summary as ProcessSummary;
    render(<ProcessAtAGlance summary={summary} labels={new Map()} onOpen={vi.fn()} />);
    const glance = screen.getByRole("region", { name: "The process at a glance" });
    expect(
      within(glance).getByText(
        "11 steps · 2 decisions · 2 approvals · 6 handoffs between 5 roles · 1 rework loop · work 14 h, waiting 120 h · process owner: Country manager",
      ),
    ).toBeInTheDocument();
    const data = glance.querySelector(".glance__line--data")?.cloneNode(true) as HTMLElement;
    data.querySelectorAll("ul").forEach((list) => list.remove());
    expect(data.textContent).toBe("3 systems · 2 of 6 handoffs by hand · 1 step off-system · 0 steps with no record");
  });

  it("test 12: the panel finds the same six handoffs the backend counts", () => {
    const steps = GRAPH.elements.filter((e) => ["activity", "decision", "approval"].includes(e.kind));
    const all = steps.flatMap((e) => handoffsFrom(e, GRAPH.elements, GRAPH.edges, new Set()));
    expect(all).toHaveLength((LEADERSHIP.summary as ProcessSummary).handoffs);
    expect(all.filter((h) => h.edge.data_move && h.edge.data_move !== "system_interface")).toHaveLength(2);
  });

  it("test 13: the comparison screen's line", () => {
    expect(deviationLine(COMPARISON)).toBe("3 of 11 steps (27%) run differently from Arden");
  });
});
