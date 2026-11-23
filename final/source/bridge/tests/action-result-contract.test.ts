import { describe, expect, it } from "vitest";

import { parseActionResult } from "../src/types.js";
import { loadFixture } from "./contract-fixtures.js";

describe("v1 Action Result contract", () => {
  it("round-trips the shared fixture", () => {
    const payload = loadFixture("valid/action-result.json");

    expect(parseActionResult(payload)).toEqual(payload);
  });

  it.each([
    "invalid/action-result-wrong-version.json",
    "invalid/action-result-missing-status.json",
    "invalid/action-result-unknown-status.json",
    "invalid/action-result-unknown-field.json",
  ])("rejects the shared invalid fixture %s", (fixture) => {
    expect(() => parseActionResult(loadFixture(fixture))).toThrow(TypeError);
  });
});
