import { describe, expect, it } from "vitest";
import { validatePublicOrigin } from "../src/public-origins.js";

describe("public origin configuration", () => {
  it("keeps exact sibling HTTPS origins and local development ports", () => {
    expect(validatePublicOrigin("https://app.scpilot.tech", true)).toBe(
      "https://app.scpilot.tech",
    );
    expect(validatePublicOrigin("http://localhost:4100", false)).toBe(
      "http://localhost:4100",
    );
  });
  it.each([
    "https://app.scpilot.tech/path",
    "https://app.scpilot.tech/",
    "https://app.scpilot.tech?other=1",
    "https://app.scpilot.tech#other",
    "https://secret@app.scpilot.tech",
    "http://app.scpilot.tech",
    "https://APP.scpilot.tech",
    "javascript:alert(1)",
    "https://*.scpilot.tech",
    "",
  ])("rejects noncanonical or unsafe configured origin %s", (value) => {
    expect(() => validatePublicOrigin(value, true)).toThrow();
  });
  it("requires HTTPS in production even on localhost", () => {
    expect(() => validatePublicOrigin("http://localhost:4100", true)).toThrow();
  });
});
