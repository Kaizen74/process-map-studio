import { describe, expect, it } from "vitest";
import {
  API_KEY_MESSAGE,
  OWNER_NAME_MESSAGE,
  validateApiKey,
  validateOwnerName,
} from "../../src/lib/validation";

const KEY = "sk-" + "ant-" + "api03-" + "a".repeat(30);

describe("validateOwnerName", () => {
  it.each(["Eric Yim", "  Eric  ", "x".repeat(80)])("accepts %s", (name) => {
    expect(validateOwnerName(name)).toBeNull();
  });
  it.each(["", "   ", "x".repeat(81), "Eric\nYim"])("refuses %j", (name) => {
    expect(validateOwnerName(name)).toBe(OWNER_NAME_MESSAGE);
  });
});

describe("validateApiKey", () => {
  it("accepts a key-shaped value, ignoring surrounding spaces", () => {
    expect(validateApiKey(`  ${KEY}\n`)).toBeNull();
  });
  it.each(["", "not-a-key", "sk-ant-short", `${KEY} extra`, "sk-openai-" + "a".repeat(30)])(
    "refuses %j",
    (key) => {
      expect(validateApiKey(key)).toBe(API_KEY_MESSAGE);
    },
  );
});
