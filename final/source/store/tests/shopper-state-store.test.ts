import { describe, expect, it } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  MemoryShopperStateStore,
  SqliteShopperStateStore,
} from "../src/shopper-state-store.js";
import { shopperStateStoreContract } from "./shopper-state-store.contract.js";

shopperStateStoreContract("memory", (options) => ({
  store: new MemoryShopperStateStore(options),
}));

shopperStateStoreContract("local SQLite file", (options) => {
  const directory = mkdtempSync(join(tmpdir(), "copilot-state-"));
  const store = new SqliteShopperStateStore(
    join(directory, "state.sqlite"),
    options,
  );
  return {
    store,
    cleanup: () => {
      store.close();
      rmSync(directory, { recursive: true, force: true });
    },
  };
});

describe("local SQLite file store", () => {
  it("keeps records, revisions and expiry across a reopen", async () => {
    const directory = mkdtempSync(join(tmpdir(), "copilot-state-"));
    const path = join(directory, "nested", "state.sqlite");
    try {
      const first = new SqliteShopperStateStore(path);
      await first.write("a", { v: 1 }, { expiresAt: Date.now() + 60_000 });
      first.close();
      const second = new SqliteShopperStateStore(path);
      expect(await second.read("a")).toMatchObject({
        value: { v: 1 },
        revision: 1,
      });
      second.close();
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
  it("lets two open stores on one file see each other and refuse stale writes", async () => {
    const directory = mkdtempSync(join(tmpdir(), "copilot-state-"));
    const path = join(directory, "state.sqlite");
    const a = new SqliteShopperStateStore(path);
    const b = new SqliteShopperStateStore(path);
    try {
      await a.write("k", { v: 1 }, { expiresAt: null, expectedRevision: null });
      expect((await b.read("k"))!.revision).toBe(1);
      expect(
        (await b.write("k", { v: 2 }, { expiresAt: null, expectedRevision: 1 }))
          .ok,
      ).toBe(true);
      expect(
        (await a.write("k", { v: 3 }, { expiresAt: null, expectedRevision: 1 }))
          .ok,
      ).toBe(false);
    } finally {
      a.close();
      b.close();
      rmSync(directory, { recursive: true, force: true });
    }
  });
});
