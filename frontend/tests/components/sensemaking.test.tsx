import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  KnowHowSection,
  OfficialLivedSection,
  StoriesSection,
  WorkTypeSection,
} from "../../src/components/panel";
import type { ElementDetail } from "../../src/lib/mapTypes";
import { seriousViolations } from "../axe";
import { SAMPLE, elementByLabel } from "../sampleMap";

// The panel's sensemaking sections (PRD §5.7.7 4a-4d; V3) on the sample, as the backend serves
// them (Appendix A.8): the SME's words first and as quotes, every anchor opening its passage.

function detail(label: string): ElementDetail {
  const found = SAMPLE.elements[elementByLabel(label).id];
  if (!found) throw new Error(label);
  return found;
}

describe("4a Work type", () => {
  it("the SME's own word first, then the work type with its quoted cues (A.8: complex, 29:48)", async () => {
    const onOpen = vi.fn();
    const { container } = render(
      <WorkTypeSection
        element={detail("Deviation in limits?")}
        onOpen={onOpen}
      />,
    );
    const section = screen.getByRole("region", { name: "Work type" });
    expect(section.firstElementChild?.nextElementSibling).toHaveTextContent(
      /^SME said: Firefighting/,
    );
    expect(within(section).getByText("Complex")).toBeInTheDocument();
    expect(within(section).getByText("proposed")).toBeInTheDocument(); // until Eric confirms
    expect(
      within(section).getByText(/enabling constraints suit it/),
    ).toBeInTheDocument();
    const cues = within(section).getByRole("list", { name: "Cues" });
    expect(
      within(cues)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual([
      "There's no fixed answer. 29:48 (open the passage)",
      "You read the situation. 29:48 (open the passage)",
    ]);
    fireEvent.click(within(cues).getAllByRole("button")[0] as HTMLElement);
    expect(onOpen).toHaveBeenCalledWith(
      expect.objectContaining({
        anchor: "29:48",
        quote: "There's no fixed answer.",
      }),
    );
    // A complex step: what the SME watches and their rules of thumb.
    expect(
      within(section).getByText("Signals watched").nextElementSibling,
    ).toHaveTextContent("the captain; the weather; what's still on the belt");
    expect(
      within(section).getByText("Rules of thumb").nextElementSibling,
    ).toHaveTextContent(
      "If the forward hold looks heavy on the plan, call the ramp before they start, not after.",
    );
    expect(
      within(section).queryByText("Typical responses"),
    ).not.toBeInTheDocument(); // none marked
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("a clear step shows its cues and no complex-step rows; an unclassified one says why", () => {
    const { rerender } = render(
      <WorkTypeSection
        element={detail("Special loads OK?")}
        onOpen={vi.fn()}
      />,
    );
    expect(screen.getByText("Clear")).toBeInTheDocument();
    expect(screen.getByText(/against the checklist/)).toBeInTheDocument();
    expect(screen.queryByText("Signals watched")).not.toBeInTheDocument();
    rerender(
      <WorkTypeSection
        element={detail("Resolve or offload")}
        onOpen={vi.fn()}
      />,
    );
    expect(screen.getByText("Not classified")).toBeInTheDocument();
    expect(
      screen.getByText(/No cue in the interviews shows the kind of work yet/),
    ).toBeInTheDocument();
    rerender(
      <WorkTypeSection
        element={detail("Deviation in limits?")}
        typicalResponses={["Accept", "Re-trim"]}
        onOpen={vi.fn()}
      />,
    );
    expect(
      screen.getByText("Typical responses").nextElementSibling,
    ).toHaveTextContent("Accept · Re-trim");
  });
});

describe("4b Know-how", () => {
  it("ASHEN in five rows with anchors, the knowledge risk and why (A.8: high at the deviation check)", () => {
    render(
      <KnowHowSection
        knowHow={detail("Deviation in limits?").know_how}
        onOpen={vi.fn()}
      />,
    );
    const rows = within(
      screen.getByRole("list", { name: "ASHEN" }),
    ).getAllByRole("listitem");
    expect(rows.map((r) => r.firstElementChild?.textContent)).toEqual([
      "Artefacts",
      "Skills",
      "Heuristics",
      "Experience",
      "Natural talent (role level)",
    ]);
    expect(rows[0]).toHaveTextContent("The loading report from Ramp.");
    expect(rows[1]).toHaveTextContent("Not described");
    expect(rows[2]).toHaveTextContent(/24:10/);
    expect(screen.getByText(/Knowledge risk:/)).toHaveTextContent(
      "Knowledge risk: High. Rules of thumb and experience outweigh documents and skills, and few roles hold them.",
    );
    expect(
      screen.getByText("Information received").nextElementSibling,
    ).toHaveTextContent("the loading report");
  });

  it("is left out where the step is not a decision point", () => {
    const { container } = render(
      <KnowHowSection
        knowHow={detail("Load and return LIR").know_how}
        onOpen={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("4c Stories", () => {
  it("the fragment in the SME's words, its type, signifier, how often, single account, anchor", () => {
    const onOpen = vi.fn();
    render(
      <StoriesSection
        stories={detail("Deviation in limits?").stories}
        onOpen={onOpen}
      />,
    );
    const card = screen
      .getByText("Had to re-trim three flights in one night")
      .closest("li") as HTMLElement;
    for (const text of [
      "Went badly",
      "Single account",
      "How often: maybe once a month",
    ]) {
      expect(within(card).getByText(text)).toBeInTheDocument();
    }
    expect(within(card).getByText(/In the SME's words:/)).toHaveTextContent(
      "Firefighting",
    );
    fireEvent.click(within(card).getByRole("button", { name: /24:10/ }));
    expect(onOpen).toHaveBeenCalledWith(
      expect.objectContaining({ anchor: "24:10" }),
    );
  });
});

describe("4d Official vs lived", () => {
  it("both accounts side by side with the question that prompted each, and both views' values (A.9)", async () => {
    const { container } = render(
      <OfficialLivedSection
        element={detail("Load and return LIR")}
        onOpen={vi.fn()}
      />,
    );
    const section = screen.getByRole("region", { name: "Official vs lived" });
    expect(
      within(section).getByText("Official").parentElement,
    ).toHaveTextContent(
      /Officially the ramp should send the report within ten minutes.*22:30.*Asked: \[M2\.4\]/,
    );
    expect(within(section).getByText("Lived").parentElement).toHaveTextContent(
      /We sometimes wait fifteen minutes for it/,
    );
    const views = within(section).getByText("Where the views differ")
      .nextElementSibling as HTMLElement;
    expect(views).toHaveTextContent(
      "TimeAs done: Up to fifteen minutes' wait for the report · As documented: Within 10 minutes of loading completion",
    );
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("'Practice not described' when only the official account exists; nothing when there is neither", () => {
    const lir = detail("Load and return LIR");
    const officialOnly = {
      ...lir,
      variants: null,
      answers: (lir.answers ?? []).filter((a) => a.account_type === "official"),
    };
    const { rerender, container } = render(
      <OfficialLivedSection element={officialOnly} onOpen={vi.fn()} />,
    );
    expect(screen.getByText("Practice not described")).toBeInTheDocument();
    rerender(
      <OfficialLivedSection
        element={detail("Issue load sheet")}
        onOpen={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
