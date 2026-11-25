import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProcessAtAGlance } from "../../src/components/leadership";
import { RaciMatrix } from "../../src/components/tabs/RaciMatrix";
import { DeciderSection } from "../../src/components/panel";
import { raciCounts, rightsOf, splits, type Rights } from "../../src/lib/accountability";
import type { ProcessSummary } from "../../src/lib/leadership";
import type { ElementDetail, GraphElement, GraphRole } from "../../src/lib/mapTypes";
import { seriousViolations } from "../axe";
import { SAMPLE, elementByLabel } from "../sampleMap";

// Who decides and who is accountable (PRD §3.20; DECISIONS 110), with the same rules as the
// backend (tests/unit/test_accountability.py runs the brief's table there too).

const ROLES: GraphRole[] = [
  ["sup", "Shift supervisor"],
  ["clc", "Certified load controller"],
  ["stn", "Station manager"],
  ["rro", "Regional roster owner"],
  ["cm", "Country manager"],
  ["rfc", "Regional finance controller"],
  ["com", "Commercial lead"],
].map(([id, name]) => ({ id: id as string, name: name as string, is_system: false, lane_order: null }));

function step(
  kind: GraphElement["kind"],
  lane: string,
  decider: string | null,
  a: [string, boolean][],
  paper: string | null = null,
): GraphElement {
  const template = elementByLabel("Approve load plan");
  return {
    ...template,
    kind,
    lane_role_id: lane,
    decision: { ...template.decision, decider_role_id: decider },
    raci: a.map(([role_id, contested]) => ({ role_id, letter: "A", contested })),
    paper_decider: paper ? { status: "named", role_id: paper, segment_id: null } : null,
  };
}

const S03 = step("approval", "sup", "sup", [["clc", false]], "clc");
const S05 = step("approval", "stn", "stn", [["rro", true]], "rro");
const S07 = step("decision", "cm", "cm", [["cm", false], ["rfc", false]]);
const S08 = step("decision", "com", null, []);

describe("decides versus accountable", () => {
  it("reads the brief's table as the backend and the Compass do", () => {
    expect(rightsOf(S03, ROLES)).toEqual({
      onPaper: "Certified load controller",
      decidedBy: "Shift supervisor",
      accountable: "Certified load controller",
      contested: false,
    });
    expect(rightsOf(S05, ROLES)?.contested).toBe(true);
    expect(rightsOf(S07, ROLES)).toMatchObject({
      accountable: "Country manager / Regional finance controller",
      contested: true,
    });
    expect(rightsOf(S08, ROLES)).toEqual({ onPaper: "", decidedBy: "Commercial lead", accountable: "", contested: false });
    expect(rightsOf(step("activity", "sup", null, []), ROLES)).toBeNull();
    expect([S03, S05, S07, S08].map((s) => splits(rightsOf(s, ROLES) as Rights))).toEqual([true, true, true, false]);
    expect(raciCounts([S03, S05, S07, S08], ROLES)).toEqual({ decisions: 4, paperDiffers: 2, split: 3, contested: 2 });
    // Case and punctuation are ignored.
    expect(splits({ onPaper: "", decidedBy: "Shift supervisor", accountable: "shift-supervisor", contested: false })).toBe(
      false,
    );
  });

  it("the RACI matrix counts above the table and marks each step where they differ", async () => {
    const { container } = render(
      <RaciMatrix graph={SAMPLE.graph} laneOrder={SAMPLE.graph.roles.map((r) => r.id)} selectedId={null} onSelect={vi.fn()} />,
    );
    expect(
      screen.getByText(
        "5 decisions · 0 decided by a different role from the documents · 1 where the one who decides is not accountable · 1 with a contested A",
      ),
    ).toBeInTheDocument();
    const marked = screen.getAllByText("decides ≠ accountable").map((m) => m.closest("tr")?.querySelector("button")?.textContent);
    expect(marked).toEqual(["Deviation in limits?"]); // decided by the load controller, A: two roles
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("the decider named in the documents", () => {
  const base = SAMPLE.elements[elementByLabel("Deviation in limits?").id] as ElementDetail;
  const graphStep = elementByLabel("Deviation in limits?");
  const rights = rightsOf(graphStep, SAMPLE.graph.roles) as Rights;
  const captain = SAMPLE.graph.roles.find((r) => r.name === "Captain")?.id ?? "";

  it("shows the three roles, the hint and nothing created", async () => {
    const detail: ElementDetail = {
      ...base,
      paper_decider: { status: "named", role_id: captain, segment_id: null },
      paper_decider_role_name: "Captain",
      paper_decider_anchor: "",
      paper_decider_hint: "The documents name a different decider. Record a Different role discrepancy?",
    };
    const { container } = render(<DeciderSection element={detail} rights={rights} roles={SAMPLE.graph.roles} />);
    const section = screen.getByRole("region", { name: "Who decides" });
    expect(within(section).getByText("Captain · not cited")).toBeInTheDocument();
    expect(within(section).getByText("Load controller")).toBeInTheDocument();
    expect(within(section).getByText(/Captain \/ Load control lead/)).toBeInTheDocument();
    expect(within(section).getByText("decides ≠ accountable")).toBeInTheDocument();
    expect(within(section).getByText(/Record a Different role discrepancy\?/)).toBeInTheDocument();
    expect(within(section).queryByRole("button")).toBeNull(); // read only without a choice
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("records a role with a cited document passage, or that none names one", () => {
    const onSave = vi.fn();
    render(
      <DeciderSection element={base} rights={rights} roles={SAMPLE.graph.roles} choice={{ busy: false, onSave }} />,
    );
    const section = screen.getByRole("region", { name: "Who decides" });
    expect(within(section).getByText("Not recorded")).toBeInTheDocument();
    fireEvent.click(within(section).getByRole("button", { name: "Record the decider named in the documents" }));
    fireEvent.change(within(section).getByLabelText("Decider named in the documents"), { target: { value: captain } });
    const passages = within(section).getByLabelText("The passage that names it") as HTMLSelectElement;
    const documentPassage = [...passages.options].find((o) => o.value !== "")?.value ?? "";
    expect(base.evidence.find((c) => c.segment_id === documentPassage)?.source_kind).not.toBe("interview_transcript");
    fireEvent.change(passages, { target: { value: documentPassage } });
    fireEvent.click(within(section).getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenLastCalledWith({ status: "named", role_id: captain, segment_id: documentPassage });
    fireEvent.click(within(section).getByRole("button", { name: "Record the decider named in the documents" }));
    fireEvent.change(within(section).getByLabelText("Decider named in the documents"), {
      target: { value: "not_named" },
    });
    fireEvent.click(within(section).getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenLastCalledWith({ status: "not_named" });
  });
});

describe("the process at a glance on the leadership view (§3.20)", () => {
  // The brief's fixture (tests 9 and 12): 11 steps, 6 handoffs between 5 roles, work 840 and
  // waiting 7,200 minutes, 3 systems, 2 handoffs by hand, 1 step off-system (D6), none D11.
  const SUMMARY: ProcessSummary = {
    process_owner: "Country manager",
    steps: 11,
    decisions: 2,
    approvals: 2,
    handoffs: 6,
    roles: 5,
    rework_loops: 1,
    work_min: 840,
    wait_min: 7200,
    timed_steps: 11,
    systems: 3,
    handoffs_known: 6,
    handoffs_manual: 2,
    off_system_steps: 1,
    no_record_steps: 0,
    steps_differing: null,
    links: {
      steps: [],
      handoffs: [],
      rework_loops: [],
      systems: ["s1", "s2", "s3"],
      handoffs_manual: ["s4", "s5"],
      off_system: ["s6"],
      no_record: [],
    },
  };
  const labels = new Map([["s6", "Re-key the bid sheet"]]);
  /** The line as read, without the step lists each figure opens. */
  const lineText = (line: Element | null) => {
    const copy = line?.cloneNode(true) as HTMLElement | undefined;
    copy?.querySelectorAll("ul").forEach((list) => list.remove());
    return copy?.textContent;
  };

  it("reads the two lines in the brief's words and opens the steps behind a data figure", async () => {
    const onOpen = vi.fn();
    const { container } = render(<ProcessAtAGlance summary={SUMMARY} labels={labels} onOpen={onOpen} />);
    const glance = screen.getByRole("region", { name: "The process at a glance" });
    expect(
      within(glance).getByText(
        "11 steps · 2 decisions · 2 approvals · 6 handoffs between 5 roles · 1 rework loop · work 14 h, waiting 120 h · process owner: Country manager",
      ),
    ).toBeInTheDocument();
    const data = glance.querySelector(".glance__line--data");
    expect(lineText(data)).toBe("3 systems · 2 of 6 handoffs by hand · 1 step off-system · 0 steps with no record");
    fireEvent.click(within(glance).getByText("1 step off-system"));
    fireEvent.click(within(glance).getByRole("button", { name: "Open Re-key the bid sheet" }));
    expect(onOpen).toHaveBeenCalledWith("s6");
    expect(within(glance).queryByText(/Times recorded on/)).toBeNull();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("says what isn't recorded rather than 0, and leaves out the Reality counts while off", () => {
    render(
      <ProcessAtAGlance
        summary={{
          ...SUMMARY,
          process_owner: "",
          work_min: 120,
          wait_min: null,
          timed_steps: 4,
          systems: null,
          handoffs_manual: null,
          off_system_steps: null,
          no_record_steps: null,
          links: { ...SUMMARY.links, systems: [], handoffs_manual: [], off_system: [] },
        }}
        labels={labels}
        onOpen={vi.fn()}
      />,
    );
    const glance = screen.getByRole("region", { name: "The process at a glance" });
    expect(glance).toHaveTextContent("work 2 h, waiting not recorded · process owner: not named");
    expect(lineText(glance.querySelector(".glance__line--data"))).toBe(
      "systems not recorded · how data moves not recorded",
    );
    expect(glance).toHaveTextContent("Times recorded on 4 of 11 steps.");
  });
});
