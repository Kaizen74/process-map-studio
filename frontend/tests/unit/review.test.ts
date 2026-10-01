import { describe, expect, it } from "vitest";
import { firstNeedingAttention, nextToReview, openSteps } from "../../src/lib/review";
import type { Graph } from "../../src/lib/mapTypes";
import { SAMPLE, elementByLabel } from "../sampleMap";

function withStatus(changes: Record<string, Partial<Graph["elements"][number]>>): Graph {
  return {
    ...SAMPLE.graph,
    elements: SAMPLE.graph.elements.map((e) => ({ ...e, ...(changes[e.label] ?? {}) })),
  };
}

const id = (label: string) => elementByLabel(label).id;

describe("auto-advance order (PRD §5.7.5)", () => {
  it("goes to the next unreviewed step in process order", () => {
    const g = withStatus({ "Draft load plan": { review_status: "confirmed" } });
    expect(nextToReview(g, id("Draft load plan"))).toBe(id("Approve load plan"));
  });

  it("takes a step the verifier only partly supported first", () => {
    const g = withStatus({ "Issue load sheet": { needs_check: true } });
    expect(nextToReview(g, id("Draft load plan"))).toBe(id("Issue load sheet"));
    expect(firstNeedingAttention(g)).toBe(id("Issue load sheet"));
  });

  it("wraps round to earlier steps and skips reviewed and rejected ones", () => {
    const g = withStatus({
      "Approve deviation": { review_status: "confirmed" },
      "Issue load sheet": { review_status: "rejected" },
    });
    expect(nextToReview(g, id("Approve deviation"))).toBe(id("Draft load plan"));
  });

  it("is null when every step is reviewed", () => {
    const done = {
      ...SAMPLE.graph,
      elements: SAMPLE.graph.elements.map((e) => ({ ...e, review_status: "confirmed" })),
    };
    expect(nextToReview(done, id("Draft load plan"))).toBeNull();
    expect(openSteps(done)).toBe(0);
    expect(openSteps(SAMPLE.graph)).toBe(10); // v1.10 A.5
  });
});
