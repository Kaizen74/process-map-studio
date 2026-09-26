import { describe, expect, it } from "vitest";
import { STATE_GLYPHS, glyphFor } from "../../src/lib/stateGlyph";

describe("state glyph mapping (PRD §5.2)", () => {
  it("matches the PRD shapes", () => {
    expect(glyphFor("supports").shape).toBe("filled-circle");
    expect(glyphFor("silent").shape).toBe("dashed-ring");
    expect(glyphFor("contradicts").shape).toBe("open-ring");
    expect(glyphFor("documented_only").shape).toBe("left-half");
    expect(glyphFor("practiced_only").shape).toBe("right-half");
    expect(glyphFor("trace_contradicted").shape).toBe("ring-cross");
    expect(glyphFor("not_assessed").shape).toBe("outlined-square");
    expect(glyphFor("contested")).toMatchObject({ shape: "open-ring", dangerText: true });
  });

  it("gives every state a sentence-case label", () => {
    for (const spec of Object.values(STATE_GLYPHS)) {
      expect(spec.label).toMatch(/^[A-Z][a-z ]+$/);
    }
  });

  it("never marks silence as a contradiction", () => {
    expect(glyphFor("silent").tone).toBe("neutral");
    expect(glyphFor("silent").shape).not.toBe(glyphFor("contradicts").shape);
  });
});
