import { readFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { validatePublicOrigin } from "../../bridge/src/public-origins.js";

export function identityConfig() {
  const production = process.env.COPILOT_ENV === "production";
  if (
    production &&
    (!process.env.COPILOT_SERVICE_SECRET ||
      process.env.COPILOT_SERVICE_SECRET.length < 32)
  )
    throw new Error("Explicit production service secret is required");
  const path = resolve(
    dirname(fileURLToPath(import.meta.url)),
    "../../work/local-identity.json",
  );
  const saved =
    !production && existsSync(path)
      ? (JSON.parse(readFileSync(path, "utf8")) as { secret?: string })
      : {};
  const secret = process.env.COPILOT_SERVICE_SECRET ?? saved.secret ?? "";
  if (secret.length < 32)
    throw new Error(
      "Run scripts/init_local_identity.py before starting services.",
    );
  const origin = process.env.COPILOT_STORE_ORIGIN ?? "http://localhost:4000";
  const panelOrigin =
    process.env.COPILOT_PANEL_ORIGIN ?? "http://localhost:4100";
  for (const raw of [origin, panelOrigin])
    validatePublicOrigin(raw, production);
  if (origin === panelOrigin)
    throw new Error("Panel and Storefront origins must differ");
  return {
    serviceSecret: secret,
    origin,
    panelOrigin,
    evaluation: !production && process.env.COPILOT_EVALUATION === "1",
  };
}
