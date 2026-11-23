import { createApp } from "./app.js";
import { identityConfig } from "./identity-config.js";
import { openCatalogue } from "./catalogue-db.js";
import {
  HOST_DIRECTORY,
  StoreEventLog,
  fileSink,
  streamSink,
} from "./event-log.js";
import { SqliteShopperStateStore } from "./shopper-state-store.js";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const port = 4000;

const repository = openCatalogue(
  process.env.COPILOT_CATALOGUE_DB ??
    resolve(
      dirname(fileURLToPath(import.meta.url)),
      "../../work/catalogue.sqlite",
    ),
);
// Shopper carts, orders and sign-in are saved in a local file so they survive a
// restart. It lives under work/ (never committed); tests use temporary files.
const stateStore = new SqliteShopperStateStore(
  process.env.COPILOT_STATE_DB ??
    resolve(
      dirname(fileURLToPath(import.meta.url)),
      "../../work/storefront-state.sqlite",
    ),
);
const catalogueRanking = process.env.CATALOGUE_RANKING ?? "lexical";
if (catalogueRanking !== "lexical" && catalogueRanking !== "hybrid")
  throw new Error("Invalid catalogue ranking");
// On the host the Storefront writes its own private log file (its systemd log folder);
// locally records print to the terminal. Neither path needs AWS credentials.
const events = new StoreEventLog(
  process.env.COPILOT_ENV === "production"
    ? fileSink(HOST_DIRECTORY)
    : streamSink(),
  process.env.COPILOT_RELEASE ?? "local",
);
createApp({
  ...identityConfig(),
  repository,
  catalogueRanking,
  events,
  stateStore,
}).listen(port, "127.0.0.1", () => {
  console.log(`Shopping Copilot Store listening on http://localhost:${port}`);
});
