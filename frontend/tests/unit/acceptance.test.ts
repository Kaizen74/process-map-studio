import { describe, expect, it } from "vitest";
import { acceptanceSentence } from "../../src/lib/acceptance";

const a = (over: Partial<Parameters<typeof acceptanceSentence>[0]>) => ({
  drafted: 0, confirmed: 0, edited: 0, rejected: 0, unreviewed: 0, added: 0, ...over,
}); // prettier-ignore

describe("how much of Claude's draft was kept (deep review item 4)", () => {
  it("names each decision once, in plain words", () => {
    expect(acceptanceSentence(a({ drafted: 10, confirmed: 6, edited: 2, rejected: 1, unreviewed: 1, added: 1 }))).toBe(
      "Of the 10 steps Claude drafted, you kept 6 as drafted, edited 2 and rejected 1; 1 isn't reviewed yet. You added 1 step yourself.",
    );
  });
  it("leaves out what didn't happen", () => {
    expect(acceptanceSentence(a({ drafted: 8, confirmed: 8 }))).toBe("Of the 8 steps Claude drafted, you kept 8 as drafted.");
    expect(acceptanceSentence(a({ drafted: 3, confirmed: 1, rejected: 2 }))).toBe(
      "Of the 3 steps Claude drafted, you kept 1 as drafted and rejected 2.",
    );
    expect(acceptanceSentence(a({ drafted: 2, unreviewed: 2 }))).toBe(
      "Of the 2 steps Claude drafted, you kept 0 as drafted; 2 aren't reviewed yet.",
    );
  });
  it("says so when Claude drafted nothing", () => {
    expect(acceptanceSentence(a({}))).toBe("Claude drafted no steps in this version.");
    expect(acceptanceSentence(a({ added: 3 }))).toBe("Claude drafted no steps in this version; you added 3 steps.");
  });
});
