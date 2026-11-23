import { describe, expect, it } from "vitest";

import { parseSnapshot } from "../src/types.js";
import { loadFixture } from "./contract-fixtures.js";

describe("v1 Snapshot contract", () => {
  it("round-trips the shared fixture without a Sensitive Field value", () => {
    const payload = loadFixture("valid/snapshot.json");

    const snapshot = parseSnapshot(payload);

    expect(snapshot).toEqual(payload);
    expect(snapshot.elements[1]).toMatchObject({ sensitive: true });
    expect(snapshot.elements[1]).not.toHaveProperty("value");
  });

  it("accepts integral JSON numbers", () => {
    const payload = loadFixture("valid/snapshot-integral-numbers.json");

    expect(parseSnapshot(payload)).toEqual(payload);
  });

  it.each([
    "invalid/snapshot-wrong-version.json",
    "invalid/snapshot-missing-url.json",
    "invalid/snapshot-sensitive-value.json",
    "invalid/snapshot-sensitive-options.json",
    "invalid/snapshot-sensitive-false.json",
    "invalid/snapshot-null-optional.json",
    "invalid/snapshot-unknown-field.json",
    "invalid/snapshot-python-field-alias.json",
  ])("rejects the shared invalid fixture %s", (fixture) => {
    expect(() => parseSnapshot(loadFixture(fixture))).toThrow(TypeError);
  });
});
