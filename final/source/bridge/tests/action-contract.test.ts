import { describe, expect, it } from "vitest";

import { parseAction } from "../src/types.js";
import { loadFixture } from "./contract-fixtures.js";

describe("v1 Action contract", () => {
  it("round-trips the shared fixture", () => {
    const payload = loadFixture("valid/action.json");

    expect(parseAction(payload)).toEqual(payload);
  });

  it("round-trips every shared Action variant", () => {
    const payloads = loadFixture("valid/action-variants.json");
    expect(Array.isArray(payloads)).toBe(true);

    expect((payloads as unknown[]).map(parseAction)).toEqual(payloads);
  });

  it("accepts integral JSON numbers", () => {
    const payload = loadFixture("valid/action-integral-numbers.json");

    expect(parseAction(payload)).toEqual(payload);
  });

  it("does not allow a model-authored read Action against any field", () => {
    expect(() =>
      parseAction({
        v: 1,
        type: "read",
        task_id: "task-safety",
        action_id: "action-read",
        sequence_number: 1,
        narration: "Read card number",
        id: 1,
      }),
    ).toThrow(TypeError);
  });

  it.each([
    "invalid/action-wrong-version.json",
    "invalid/action-missing-task-id.json",
    "invalid/action-unknown-type.json",
    "invalid/action-fractional-sequence.json",
    "invalid/action-unsafe-integer.json",
    "invalid/action-unknown-field.json",
  ])("rejects the shared invalid fixture %s", (fixture) => {
    expect(() => parseAction(loadFixture(fixture))).toThrow(TypeError);
  });
});
