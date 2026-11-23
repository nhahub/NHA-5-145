import request from "supertest";
import { afterEach, expect, it, vi } from "vitest";
import { createApp } from "./app.js";
import { identityConfig } from "../src/identity-config.js";

afterEach(() => vi.unstubAllEnvs());
const origin = "https://store.scpilot.tech";
const panelOrigin = "https://app.scpilot.tech";
it("publishes only configured public Bridge origins in personal HTML", async () => {
  const app = createApp({
    origin,
    panelOrigin,
    serviceSecret: "test-service-secret-that-must-not-appear-in-HTML",
  });
  const response = await request(app).get("/");
  expect(response.text).toContain(
    '<meta name="copilot-panel-origin" content="https://app.scpilot.tech"',
  );
  expect(response.text).toContain(
    '<meta name="copilot-store-origin" content="https://store.scpilot.tech"',
  );
  expect(response.text).not.toContain("test-service-secret");
  expect(response.headers["cache-control"]).toBe("no-store");
});
it("rejects unsafe public metadata before serving the Storefront", () => {
  expect(() =>
    createApp({ origin, panelOrigin: 'https://app.example/"<script>' }),
  ).toThrow();
});
it("production refuses evaluation routes even with evaluation enabled", async () => {
  vi.stubEnv("COPILOT_ENV", "production");
  const app = createApp({ origin, panelOrigin, evaluation: true });
  expect((await request(app).post("/__test/reset")).status).toBe(404);
  expect((await request(app).get("/__test/state")).status).toBe(404);
});
it("production requires an explicit service secret instead of the development file", () => {
  vi.stubEnv("COPILOT_ENV", "production");
  vi.stubEnv("COPILOT_SERVICE_SECRET", "");
  expect(() => identityConfig()).toThrow(/production/i);
});
