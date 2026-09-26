import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime, plural, sentence } from "../../src/lib/format";

describe("display formats", () => {
  it("formats dates the same way in every browser", () => {
    expect(formatDate("2026-09-26T10:00:00")).toBe("26 Sep 2026");
    expect(formatDate("not a date")).toBe("not a date");
  });

  it("pluralises and sentence-cases", () => {
    expect(plural(1, "source")).toBe("1 source");
    expect(plural(3, "source")).toBe("3 sources");
    expect(plural(2, "speaker", "speakers")).toBe("2 speakers");
    expect(sentence("published")).toBe("Published");
    expect(sentence("")).toBe("");
  });
});

describe("formatDateTime", () => {
  it("shows the local date and time, or the raw text if it can't be read", () => {
    const local = new Date(2026, 8, 26, 9, 5).toISOString();
    expect(formatDateTime(local)).toBe("26 Sep 2026, 09:05");
    expect(formatDateTime("soon")).toBe("soon");
  });
});
