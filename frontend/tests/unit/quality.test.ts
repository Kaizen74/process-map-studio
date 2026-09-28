import { describe, expect, it } from "vitest";
import { ApiError } from "../../src/api/request";
import { blockersOf, greenCount } from "../../src/lib/quality";
import type { QualityCard } from "../../src/lib/reviewTypes";

const check = (id: string, status: "pass" | "fail" | "warning", hard = true) => ({ id, name: id, status, hard, detail: "" });

describe("quality card helpers (PRD §5.7.1, §5.7.9)", () => {
  it("counts the hard checks that pass; Q10 is only a warning", () => {
    const card: QualityCard = {
      checks: [check("Q1", "pass"), check("Q6", "fail"), check("Q10", "warning", false)],
      warnings: [],
      all_green: false,
    };
    expect(greenCount(card)).toEqual({ green: 1, total: 2 });
  });

  it("reads the blockers of a refused publish, and nothing else", () => {
    const blocker = { type: "unreviewed_element", id: "e1", element_id: "e1", message: "“A” hasn't been reviewed yet." };
    const refused = new ApiError("PUBLISH_BLOCKED", "Can't publish.", 409, { blockers: [blocker] }, "r1");
    expect(blockersOf(refused)).toEqual([blocker]);
    expect(blockersOf(new ApiError("CONFLICT", "No.", 409, {}, ""))).toBeNull();
    expect(blockersOf(new Error("x"))).toBeNull();
  });
});
