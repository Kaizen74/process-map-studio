import { describe, expect, it } from "vitest";
import { ApiError } from "../../src/api/request";
import { copyDetailsOf, messageOf } from "../../src/lib/errors";

describe("error helpers", () => {
  it("gives Copy details only when the API supplied them", () => {
    expect(copyDetailsOf(new ApiError("IO", "m", 500, {}, "r1"))).toBe("IO · request r1");
    expect(copyDetailsOf(new Error("plain"))).toBeUndefined();
    expect(copyDetailsOf(null)).toBeUndefined();
  });

  it("always has a message to show", () => {
    expect(messageOf(new Error("Saved nothing."))).toBe("Saved nothing.");
    expect(messageOf("weird")).toMatch(/Something went wrong/);
  });
});
