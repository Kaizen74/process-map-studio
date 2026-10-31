import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  AiFlag,
  AllReviewed,
  ConfidenceBreakdown,
  ConstraintList,
  DecisionRights,
  EvidenceCard,
  HandoffTime,
  PanelHeader,
  ReviewActions,
  RoleAccountability,
} from "../../src/components/panel";
import type { ElementDetail } from "../../src/lib/mapTypes";
import { seriousViolations } from "../axe";
import { SAMPLE, elementByLabel } from "../sampleMap";

function detail(label: string): ElementDetail {
  const found = SAMPLE.elements[elementByLabel(label).id];
  if (!found) throw new Error(label);
  return found;
}

describe("evidence cards (PRD §5.7.7 section 1)", () => {
  it("a cited passage opens the viewer; it shows stance, source, anchor and the quote", () => {
    const onOpen = vi.fn();
    const [card] = detail("Load and return LIR").evidence;
    if (!card) throw new Error("no card");
    render(<EvidenceCard card={card} onOpen={onOpen} />);
    const button = screen.getByRole("button", { name: /Open interview_transcript.txt at 21:50/ });
    expect(within(button).getByText("Supports")).toBeInTheDocument();
    expect(within(button).getByText("21:50")).toHaveClass("mono");
    expect(within(button).getByText(/^“Ramp loads the aircraft/)).toBeInTheDocument();
    fireEvent.click(button);
    expect(onOpen).toHaveBeenCalledWith(card);
  });

  it("a contradicting passage shows its divergence in danger text", () => {
    const card = detail("Load and return LIR").evidence.find((c) => c.stance === "contradicts");
    if (!card) throw new Error("no card");
    render(<EvidenceCard card={card} onOpen={vi.fn()} />);
    expect(screen.getByText("Contradicts")).toBeInTheDocument();
    expect(screen.getByText(/Threshold divergence: 10 min in the SOP/)).toHaveClass("evidence__note");
  });

  it("a silent source is grey, says silence is not contradiction, and can't be clicked", () => {
    const onOpen = vi.fn();
    const card = detail("Load and return LIR").evidence.find((c) => c.stance === "silent");
    if (!card) throw new Error("no card");
    const { container } = render(<EvidenceCard card={card} onOpen={onOpen} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText(/Silence is not contradiction/)).toBeInTheDocument();
    expect(container.firstElementChild).toHaveClass("evidence--silent");
    fireEvent.click(container.firstElementChild as Element);
    expect(onOpen).not.toHaveBeenCalled();
  });
});

describe("panel sections", () => {
  it("confidence: one line per term, and a total equal to the value shown", () => {
    const lir = detail("Load and return LIR");
    render(<ConfidenceBreakdown element={lir} />);
    // A.10 (C3): the landscape interview is one more independent source; the cap still holds.
    expect(screen.getByText("1 more independent source supports").nextElementSibling).toHaveTextContent("+0.15");
    expect(screen.getByText("Capped at 0.60 while contested").nextElementSibling).toHaveTextContent("−0.25");
    expect(screen.getByText("Observed (O)").nextElementSibling).toHaveTextContent("+0.60");
    expect(screen.getByText("Confidence").nextElementSibling).toHaveTextContent("0.60");
    for (const element of Object.values(SAMPLE.elements)) {
      if (element.confidence === null) continue;
      const sum = element.confidence_breakdown.reduce((total, t) => total + t.delta, 0);
      expect(Math.round(sum * 100) / 100).toBe(element.confidence);
    }
  });

  it("start and end have no confidence section", () => {
    const { container } = render(<ConfidenceBreakdown element={detail("Flight scheduled")} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("a contested accountable role shows as A? in danger text, naming each side's sources", () => {
    render(<RoleAccountability element={detail("Deviation in limits?")} />);
    const letters = screen.getAllByText("A?");
    expect(letters).toHaveLength(2);
    expect(letters[0]).toHaveClass("raci-letter--contested");
    expect(screen.getByText("R")).not.toHaveClass("raci-letter--contested");
    expect(
      screen.getByText(
        "Accountability is contested: Captain (interview_transcript.txt 27:15) vs Load control lead (sop_LC-07.docx §5).",
      ),
    ).toHaveClass("panel-danger");
  });

  it("decision rights: mechanism, decider, rule and escalation", () => {
    render(<DecisionRights element={detail("Deviation in limits?")} />);
    expect(screen.getByText("Judgment")).toBeInTheDocument();
    expect(screen.getByText("Load controller")).toBeInTheDocument();
    expect(screen.getByText("Weight deviation within the airline contract tolerance")).toBeInTheDocument();
    expect(screen.getByText("Outside tolerance the captain decides")).toBeInTheDocument();
    const { container } = render(<DecisionRights element={detail("Draft load plan")} />);
    expect(container).toBeEmptyDOMElement(); // activities have no decision rights
  });

  it("handoff and time side by side; a step without time says so", () => {
    render(<HandoffTime element={detail("Load and return LIR")} />);
    expect(screen.getByText("Loading report to the Load controller")).toBeInTheDocument();
    expect(screen.getByText("~40 min")).toBeInTheDocument();
    expect(screen.getByText("15 min")).toBeInTheDocument();
    render(<HandoffTime element={detail("Issue load sheet")} />);
    expect(screen.getByText("Around T-15")).toBeInTheDocument();
  });

  it("constraints: key ones with a coral dot, cause type and provenance", () => {
    const { container } = render(<ConstraintList element={detail("Load and return LIR")} />);
    expect(container.querySelectorAll(".constraint-dot:not(.constraint-dot--plain)")).toHaveLength(2);
    // A.10 (C3): + the landscape interview's weakness (the report keyed into a separate system).
    expect(screen.getAllByText("System fragmentation · provenance O")).toHaveLength(2);
    expect(screen.getAllByText("Key constraint:")).toHaveLength(2);
  });

  it("AI flag: the five-field block in plain words", () => {
    render(<AiFlag element={detail("Load and return LIR")} />);
    for (const text of ["Perception", "Paper loading report", "Keyed loading data", "Rule-based: an automation candidate"]) {
      expect(screen.getByText(text)).toBeInTheDocument();
    }
  });

  it("the header chips follow the PRD order and mark contested and unreviewed", () => {
    const deviation = elementByLabel("Deviation in limits?");
    render(<PanelHeader element={deviation} laneName="Load controller" phaseName="Close out" />);
    expect(screen.getByText("Decision · Close out")).toBeInTheDocument();
    expect(screen.getByText("Contested")).toHaveClass("chip--danger");
    expect(screen.getByText("Divergence · ownership")).toHaveClass("chip--danger");
    expect(screen.getByText("Unreviewed")).toHaveClass("chip--dashed");
    expect(screen.queryByText(/^Part of:/)).toBeNull();
  });

  it("a practice step says which landscape activity it is part of (K2)", () => {
    render(<PanelHeader element={elementByLabel("Draft load plan")} laneName="Load controller" phaseName="Plan" partOf="Manage loading" />);
    expect(screen.getByText("Part of: Manage loading")).toBeInTheDocument();
  });

  it("has no serious accessibility problems", async () => {
    const lir = detail("Load and return LIR");
    const { container } = render(
      <div>
        <ConfidenceBreakdown element={lir} />
        <HandoffTime element={lir} />
        <ConstraintList element={lir} />
        <AiFlag element={lir} />
        {lir.evidence.map((card, i) => (
          <EvidenceCard key={i} card={card} onOpen={vi.fn()} />
        ))}
      </div>,
    );
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("review actions (PRD §5.7.5)", () => {
  function draw(status: string, needsCheck = false) {
    const handlers = { onConfirm: vi.fn(), onReject: vi.fn(), onRestore: vi.fn(), onEdit: vi.fn() };
    render(<ReviewActions status={status} needsCheck={needsCheck} busy={false} {...handlers} />);
    return handlers;
  }

  it("an unreviewed step offers Confirm as drafted, Edit and Reject step", () => {
    const h = draw("draft");
    expect(screen.getByText(/Confirming locks this step/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm as drafted" }));
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.click(screen.getByRole("button", { name: "Reject step" }));
    expect([h.onConfirm, h.onEdit, h.onReject].map((f) => f.mock.calls.length)).toEqual([1, 1, 1]);
    expect(screen.queryByText(/only partial support/)).toBeNull();
  });

  it("warns before confirming a step the verifier only partly supported", () => {
    draw("draft", true);
    expect(screen.getByText(/found only partial support/)).toHaveClass("panel-danger");
  });

  it("a reviewed step is locked, with an Edit link", () => {
    const h = draw("edited");
    expect(screen.getByRole("status")).toHaveTextContent("Edited · locked against AI re-runs");
    expect(screen.queryByRole("button", { name: "Confirm as drafted" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(h.onEdit).toHaveBeenCalled();
  });

  it("a rejected step explains itself and can be restored", () => {
    const h = draw("rejected");
    expect(screen.getByRole("status")).toHaveTextContent(/Rejected\. Its connected steps may now be orphaned/);
    fireEvent.click(screen.getByRole("button", { name: "Restore" }));
    expect(h.onRestore).toHaveBeenCalled();
  });

  it("says when every step is reviewed", () => {
    render(<AllReviewed />);
    expect(screen.getByText("All steps reviewed")).toBeInTheDocument();
    // The quality card and Publish are here now (Eric's Export cargo screenshot, 2026-10-29).
    expect(screen.getByRole("status")).toHaveTextContent(
      "Every step is confirmed, edited, added or rejected. Check the quality card at the top, then publish.",
    );
    expect(screen.queryByText(/build phase/)).toBeNull();
  });
});
