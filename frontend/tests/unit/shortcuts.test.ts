import { describe, expect, it } from "vitest";
import { shortcutFor, stepAlong } from "../../src/lib/shortcuts";

const press = (key: string, target: EventTarget | null = document.body, mods: Partial<Record<"ctrlKey" | "altKey" | "metaKey", boolean>> = {}) => ({
  key,
  target,
  ctrlKey: false,
  altKey: false,
  metaKey: false,
  ...mods,
});

describe("review shortcuts (PRD §5.8)", () => {
  it.each([
    ["j", "next"],
    ["J", "next"],
    ["k", "previous"],
    ["c", "confirm"],
    ["e", "edit"],
    ["R", "reject"],
    ["?", "help"],
    ["Escape", "close"],
  ])("%s → %s", (key, kind) => {
    expect(shortcutFor(press(key))?.kind).toBe(kind);
  });

  it("1–6 switch lens in toolbar order", () => {
    expect(["1", "2", "3", "4", "5", "6"].map((k) => shortcutFor(press(k)))).toEqual([
      { kind: "lens", lens: "plain" },
      { kind: "lens", lens: "source_state" },
      { kind: "lens", lens: "confidence" },
      { kind: "lens", lens: "time" },
      { kind: "lens", lens: "work_type" }, // V2
      { kind: "lens", lens: "exceptions" }, // X3
    ]);
    expect(shortcutFor(press("7"))).toBeNull();
  });

  it("is ignored while typing, and with Ctrl, Alt or Command held", () => {
    for (const tag of ["input", "textarea", "select"]) {
      expect(shortcutFor(press("c", document.createElement(tag)))).toBeNull();
      expect(shortcutFor(press("Escape", document.createElement(tag)))).toBeNull();
    }
    expect(shortcutFor(press("c", document.body, { ctrlKey: true }))).toBeNull();
    expect(shortcutFor(press("r", document.body, { metaKey: true }))).toBeNull();
    expect(shortcutFor(press("1", document.body, { altKey: true }))).toBeNull();
    expect(shortcutFor(press("x"))).toBeNull();
  });

  it("J and K walk the process order and stop at the ends", () => {
    const ids = ["a", "b", "c"];
    expect(stepAlong(ids, null, 1)).toBe("a");
    expect(stepAlong(ids, null, -1)).toBe("c");
    expect(stepAlong(ids, "a", 1)).toBe("b");
    expect(stepAlong(ids, "c", 1)).toBe("c");
    expect(stepAlong(ids, "a", -1)).toBe("a");
    expect(stepAlong(ids, "gone", 1)).toBe("a");
    expect(stepAlong([], null, 1)).toBeNull();
  });
});
