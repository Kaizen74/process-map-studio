import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DraftState } from "../../src/api/types";
import { WalkthroughStrip } from "../../src/components/map";
import { stepsWithImages, walkthroughCards, type StepImage } from "../../src/lib/images";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp } from "../renderApp";
import { SAMPLE, elementByLabel, layoutFor } from "../sampleMap";

const VID = SAMPLE.graph.version.id;
const STEP_KINDS = new Set(["activity", "decision", "approval"]);
const STEPS = SAMPLE.graph.elements.filter((e) => STEP_KINDS.has(e.kind));

function picture(id: string, label: string, change: Partial<StepImage> = {}): StepImage {
  return {
    id,
    element_id: elementByLabel(label).id,
    caption: `Picture ${id}`,
    image_type: "workplace_photo",
    origin: "uploaded",
    status: "kept",
    redaction_confirmed: true,
    source_name: "",
    page: null,
    created_at: "2026-09-28T09:00:00+00:00",
    ...change,
  };
}

// Two steps from the sample, later one first, to show the strip follows process order.
const FIRST = STEPS[0]?.label ?? "";
const LATER = STEPS[3]?.label ?? "";

describe("which pictures the strip and the marker show", () => {
  it("the strip: kept pictures only, in process order, numbered among the steps", () => {
    const images = [
      picture("a", LATER),
      picture("b", FIRST),
      picture("c", FIRST, { status: "suggested", origin: "extracted" }),
      picture("d", FIRST, { status: "discarded", origin: "extracted" }),
    ];
    const cards = walkthroughCards(SAMPLE.graph.elements, images);
    expect(cards.map((c) => [c.image.id, c.stepNumber, c.stepName])).toEqual([
      ["b", 1, FIRST],
      ["a", 4, LATER],
    ]);
  });

  it("pictures on a rejected step leave the strip", () => {
    const elements = SAMPLE.graph.elements.map((e) => (e.label === FIRST ? { ...e, review_status: "rejected" } : e));
    expect(walkthroughCards(elements, [picture("b", FIRST)])).toEqual([]);
  });

  it("the marker: any picture that isn't discarded, suggestions included", () => {
    const found = stepsWithImages([
      picture("a", LATER, { status: "discarded" }),
      picture("c", FIRST, { status: "suggested", origin: "extracted" }),
    ]);
    expect([...found]).toEqual([elementByLabel(FIRST).id]);
  });
});

describe("the walkthrough strip (PRD §5.7.11)", () => {
  const cards = walkthroughCards(SAMPLE.graph.elements, [picture("a", LATER), picture("b", FIRST)]);

  it("is hidden when there are no pictures", () => {
    const { container } = render(<WalkthroughStrip cards={[]} selectedId={null} onSelect={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("200 px cards with the picture, Step n · name and the caption; a click selects the step", async () => {
    const onSelect = vi.fn();
    const { container } = render(
      <WalkthroughStrip cards={cards} selectedId={elementByLabel(LATER).id} onSelect={onSelect} />,
    );
    const strip = screen.getByRole("region", { name: "Visual walkthrough" });
    expect(strip).toHaveTextContent("In-app only · never exported · metadata stripped");
    const [first, second] = within(strip).getAllByRole("button");
    if (!first || !second) throw new Error("two cards");
    expect(first).toHaveAccessibleName(`Step 1 · ${FIRST} Picture b`);
    expect(first.querySelector("img")).toHaveAttribute("src", "/api/images/b/file?size=thumb");
    expect(first).toHaveAttribute("aria-pressed", "false");
    expect(second).toHaveAttribute("aria-pressed", "true");
    expect(second).toHaveClass("walkthrough__card--selected");
    fireEvent.click(first);
    expect(onSelect).toHaveBeenCalledWith(elementByLabel(FIRST).id);
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("a picture that can't be shown becomes a striped placeholder naming its type", () => {
    render(<WalkthroughStrip cards={cards} selectedId={null} onSelect={vi.fn()} />);
    const [first] = screen.getAllByRole("button");
    if (!first) throw new Error("a card");
    fireEvent.error(first.querySelector("img") as HTMLImageElement);
    expect(first.querySelector("img")).toBeNull();
    expect(within(first).getByText("Workplace photo")).toBeInTheDocument();
  });
});

describe("pictures on the Review screen", () => {
  const DRAFTED: DraftState = {
    job: null,
    version: { id: VID, engagement_id: "e1", label: "v0.1", state: "draft", created_at: "2026-09-27T10:00:00+00:00" },
    summary: { steps: 8, needs_check: 0, verified: 21, rejected: 0, open_questions: 5, scrubbed: 0 },
  };

  beforeEach(() => window.localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  function backend(images: StepImage[]) {
    return fakeApi({
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/draft": () => ({ body: DRAFTED }),
      [`GET /api/versions/${VID}/graph`]: () => ({ body: SAMPLE.graph }),
      [`GET /api/versions/${VID}/layout`]: (_body, url) => ({ body: layoutFor(url) }),
      [`GET /api/versions/${VID}/images`]: () => ({ body: images }),
      ...Object.fromEntries(
        Object.entries(SAMPLE.elements).map(([id, element]) => [`GET /api/elements/${id}`, () => ({ body: element })]),
      ),
    });
  }

  it("a step with a picture has the marker and says so; the strip selects the step", async () => {
    backend([picture("b", FIRST), picture("c", LATER, { status: "suggested", origin: "extracted" })]);
    const { container } = renderApp("/engagements/e1/review");
    const node = await screen.findByRole("button", { name: new RegExp(`, ${FIRST},.*, has images$`) });
    expect(node.querySelector(".map-marker--images")).not.toBeNull();
    // The suggestion is not yet in the strip, but its step has the marker.
    const later = screen.getByRole("button", { name: new RegExp(`, ${LATER},.*, has images$`) });
    expect(later.querySelector(".map-marker--images")).not.toBeNull();
    const others = container.querySelectorAll(".map-marker--images");
    expect(others).toHaveLength(2);
    const strip = screen.getByRole("region", { name: "Visual walkthrough" });
    const cards = within(strip).getAllByRole("button");
    expect(cards).toHaveLength(1);
    fireEvent.click(cards[0] as HTMLElement);
    expect(await screen.findByRole("heading", { level: 2, name: FIRST })).toBeInTheDocument();
    expect(within(strip).getByRole("button")).toHaveAttribute("aria-pressed", "true");
  });

  it("no pictures: no markers and no strip", async () => {
    backend([]);
    const { container } = renderApp("/engagements/e1/review");
    await screen.findByRole("button", { name: new RegExp(`, ${FIRST},`) });
    expect(container.querySelector(".map-marker--images")).toBeNull();
    expect(screen.queryByRole("region", { name: "Visual walkthrough" })).toBeNull();
  });
});
