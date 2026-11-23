import { defineConfig } from "vite";
import { validatePublicOrigin } from "../bridge/src/public-origins.js";

const production = process.env.COPILOT_ENV === "production";
if (
  production &&
  (!process.env.COPILOT_PANEL_ORIGIN || !process.env.COPILOT_STORE_ORIGIN)
)
  throw new Error("Production Panel build requires explicit public origins");
const panel = validatePublicOrigin(
  process.env.COPILOT_PANEL_ORIGIN ?? "http://localhost:4100",
  production,
);
const store = validatePublicOrigin(
  process.env.COPILOT_STORE_ORIGIN ?? "http://localhost:4000",
  production,
);
const agent = validatePublicOrigin(
  process.env.COPILOT_AGENT_ORIGIN ??
    (production ? panel : "http://localhost:8000"),
  production,
);
if (panel === store || (production && agent !== panel))
  throw new Error(
    "Panel and Storefront require separate origins; production Agent shares Panel origin",
  );

export default defineConfig({
  define: {
    __COPILOT_PUBLIC_ORIGINS__: JSON.stringify({ panel, store, agent }),
  },
});
