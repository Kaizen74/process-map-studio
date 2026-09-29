import { describe, expect, it } from "vitest";
import { barWidths, confidenceText, minutes, weightText, type PhaseFacts } from "../../src/lib/leadership";

const phase = (work: number, wait: number): PhaseFacts => ({
  phase_id: "p",
  name: "P",
  work_min: work,
  wait_min: wait,
  rework_loops: 0,
  handoffs: 0,
  divergence_counts: {},
  links: { work: [], wait: [], rework_loops: [], handoffs: [], divergence: {} },
});

describe("leadership words and bars", () => {
  it("bars are shares of the longest phase, work and wait apart", () => {
    expect(barWidths([phase(20, 0), phase(80, 15), phase(15, 0)])).toEqual([
      { work: (20 / 95) * 100, wait: 0 },
      { work: (80 / 95) * 100, wait: (15 / 95) * 100 },
      { work: (15 / 95) * 100, wait: 0 },
    ]);
    expect(barWidths([phase(0, 0)])).toEqual([{ work: 0, wait: 0 }]);
  });

  it("plain words for minutes, evidence weight and confidence", () => {
    expect(minutes(20)).toBe("20 min");
    expect(minutes(1.25)).toBe("1.3 min");
    expect(weightText({ supporting: 3, sources: 5 })).toBe("Supported by 3 of 5 sources");
    expect(weightText({ supporting: 1, sources: 1 })).toBe("Supported by 1 of 1 source");
    expect(confidenceText(0.72)).toBe("Confidence 72%");
    expect(confidenceText(null)).toBe("Confidence not worked out");
  });
});
