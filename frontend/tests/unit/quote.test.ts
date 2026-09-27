import { describe, expect, it } from "vitest";
import { quoteRange } from "../../src/lib/quote";

const TEXT = "Ramp loads the aircraft, forty minutes or so, and sends back the “loading report”. Then we wait.";

function marked(text: string, quote: string): string | null {
  const range = quoteRange(text, quote);
  return range ? text.slice(range[0], range[1]) : null;
}

describe("quote highlight (PRD §5.7.8)", () => {
  it("finds the quote as written", () => {
    expect(marked(TEXT, "forty minutes or so")).toBe("forty minutes or so");
  });

  it("ignores case, extra spaces and curly or straight quote marks", () => {
    expect(marked(TEXT, "RAMP loads  the aircraft")).toBe("Ramp loads the aircraft");
    expect(marked(TEXT, 'sends back the "loading report"')).toBe("sends back the “loading report”");
  });

  it("allows a trailing full stop the passage doesn't have in that place", () => {
    expect(marked("It takes forty minutes, give or take", "It takes forty minutes.")).toBe("It takes forty minutes");
  });

  it("gives nothing when the quote isn't there or is empty", () => {
    expect(quoteRange(TEXT, "thirty minutes")).toBeNull();
    expect(quoteRange(TEXT, "  ")).toBeNull();
    expect(marked(TEXT, "“Then we wait.”")).toBe("Then we wait."); // marks around the whole quote
  });
});
