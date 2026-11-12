import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GradeControl } from "../../src/components/common";
import { FindingCard } from "../../src/components/gap";
import { PanelHeader } from "../../src/components/panel";
import { VersionBanner } from "../../src/components/shell";
import type { Grade } from "../../src/lib/grade";
import { seriousViolations } from "../axe";
import { SAMPLE, elementByLabel } from "../sampleMap";
import { finding } from "../unit/gap.test";

afterEach(cleanup);

const SUGGESTED: Grade = { grade: "indicated", suggested: "indicated", chosen_by_owner: false, rules_version: "1" };
const CHOSEN: Grade = { ...SUGGESTED, grade: "confirmed", chosen_by_owner: true };

// Shared language with the other apps (2026-11-12, Eric's brief; DECISIONS 96).
describe("the shared grade", () => {
  it("shows the suggested grade in words and lets Eric choose another", async () => {
    const onChange = vi.fn();
    const { container } = render(<GradeControl grade={SUGGESTED} subject="X1" onChange={onChange} />);
    expect(screen.getByText("Grade: Indicated")).toBeInTheDocument();
    expect(screen.getByText("(suggested)")).toBeInTheDocument();
    const list = screen.getByLabelText("Grade for X1");
    expect([...list.querySelectorAll("option")].map((o) => o.textContent)).toEqual([
      "Confirmed",
      "Indicated",
      "Hypothesis",
    ]);
    fireEvent.change(list, { target: { value: "hypothesis" } });
    expect(onChange).toHaveBeenCalledWith("hypothesis");
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("says when the grade is Eric's own, and choosing the suggested one again clears his choice", () => {
    const onChange = vi.fn();
    render(<GradeControl grade={CHOSEN} subject="X1" onChange={onChange} />);
    expect(screen.getByText("Grade: Confirmed")).toBeInTheDocument();
    expect(screen.getByText("(your choice; suggested: Indicated)")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Grade for X1"), { target: { value: "indicated" } });
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("is read only where the grade was frozen with a published version", () => {
    render(<GradeControl grade={SUGGESTED} subject="X1" />);
    expect(screen.getByText("Grade: Indicated")).toBeInTheDocument();
    expect(screen.queryByLabelText("Grade for X1")).toBeNull();
  });

  it("a gap finding carries its grade and passes Eric's choice on; a finalised report only shows it", () => {
    const onGrade = vi.fn();
    const f = finding({ grade: SUGGESTED });
    const props = { finding: f, mode: "internal" as const, onGoTo: vi.fn(), onOpenSource: vi.fn(), onDecide: vi.fn() };
    const { rerender } = render(<FindingCard {...props} locked={false} onGrade={onGrade} />);
    fireEvent.change(screen.getByLabelText(`Grade for ${f.title}`), { target: { value: "confirmed" } });
    expect(onGrade).toHaveBeenCalledWith(f, "confirmed");
    rerender(<FindingCard {...props} locked onGrade={onGrade} />);
    expect(screen.getByText("Grade: Indicated")).toBeInTheDocument();
    expect(screen.queryByLabelText(`Grade for ${f.title}`)).toBeNull();
  });
});

describe("shared codes on the map", () => {
  it("every step of the sample has its code and start and end have none", () => {
    const steps = SAMPLE.graph.elements.filter((e) => e.kind !== "start" && e.kind !== "end");
    expect(steps.map((e) => e.code)).toEqual(steps.map((_, i) => `S-${String(i + 1).padStart(2, "0")}`));
    expect(SAMPLE.graph.elements.filter((e) => e.kind === "start" || e.kind === "end").map((e) => e.code)).toEqual([
      null,
      null,
    ]);
  });

  it("the step panel shows the code before the kind and phase", () => {
    render(<PanelHeader element={elementByLabel("Draft load plan")} laneName="Load controller" phaseName="Plan" />);
    expect(screen.getByText("S-01 · Activity · Plan")).toBeInTheDocument();
  });

  it("a map from a hand-off shows its key and pilot in the banner; a map without one shows neither", () => {
    const props = { label: "v1", sources: 2, steps: [], selectedId: null, onSelect: vi.fn() };
    const { rerender } = render(<VersionBanner {...props} handoff={{ key: "MERIDIAN", pilot: "VS-01" }} />);
    expect(screen.getByText("MERIDIAN · VS-01")).toBeInTheDocument();
    rerender(<VersionBanner {...props} />);
    expect(screen.queryByText(/MERIDIAN/)).toBeNull();
  });
});
