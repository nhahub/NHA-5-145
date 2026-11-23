import { describe, expect, it, afterEach } from "vitest";
import {
  RecordTooLargeError,
  type ShopperStateStore,
} from "../src/shopper-state-store.js";

export interface StoreHarness {
  store: ShopperStateStore;
  /** Release files or connections. */
  cleanup?: () => void;
}

/**
 * The storage contract every Shopper State Store must keep (memory, local file and,
 * later, the DynamoDB adapter). A factory builds a fresh empty store that reads time
 * from `clock` and refuses records above `maxRecordBytes`.
 */
export function shopperStateStoreContract(
  name: string,
  create: (options: {
    clock: () => number;
    maxRecordBytes: number;
  }) => StoreHarness,
): void {
  describe(`Shopper State Store contract: ${name}`, () => {
    const cleanups: (() => void)[] = [];
    let now = 1_000;
    afterEach(() => {
      for (const done of cleanups.splice(0)) done();
    });
    function fresh(maxRecordBytes = 4096): ShopperStateStore {
      now = 1_000;
      const harness = create({ clock: () => now, maxRecordBytes });
      cleanups.push(() => harness.cleanup?.());
      return harness.store;
    }

    it("reads nothing for a missing key", async () => {
      expect(await fresh().read("a")).toBeUndefined();
    });

    it("writes and reads back a JSON document with its revision and expiry", async () => {
      const store = fresh();
      const result = await store.write(
        "a",
        { سلة: [1, "x"], n: null },
        { expiresAt: 5_000, expectedRevision: null },
      );
      expect(result).toEqual({ ok: true, revision: 1 });
      expect(await store.read("a")).toEqual({
        value: { سلة: [1, "x"], n: null },
        revision: 1,
        expiresAt: 5_000,
      });
    });

    it("creates only when absent when the expected revision is null", async () => {
      const store = fresh();
      await store.write(
        "a",
        { v: 1 },
        { expiresAt: null, expectedRevision: null },
      );
      const again = await store.write(
        "a",
        { v: 2 },
        { expiresAt: null, expectedRevision: null },
      );
      expect(again.ok).toBe(false);
      expect((await store.read("a"))!.value).toEqual({ v: 1 });
    });

    it("refuses a stale revision and accepts the current one", async () => {
      const store = fresh();
      await store.write("a", { v: 1 }, { expiresAt: null });
      const next = await store.write(
        "a",
        { v: 2 },
        { expiresAt: null, expectedRevision: 1 },
      );
      expect(next).toEqual({ ok: true, revision: 2 });
      const stale = await store.write(
        "a",
        { v: 3 },
        { expiresAt: null, expectedRevision: 1 },
      );
      expect(stale.ok).toBe(false);
      expect(await store.read("a")).toMatchObject({
        value: { v: 2 },
        revision: 2,
      });
    });

    it("refuses a revision for a key that does not exist", async () => {
      const store = fresh();
      const result = await store.write(
        "a",
        { v: 1 },
        { expiresAt: null, expectedRevision: 3 },
      );
      expect(result.ok).toBe(false);
      expect(await store.read("a")).toBeUndefined();
    });

    it("writes unconditionally when no revision is expected", async () => {
      const store = fresh();
      await store.write("a", { v: 1 }, { expiresAt: null });
      expect(await store.write("a", { v: 2 }, { expiresAt: null })).toEqual({
        ok: true,
        revision: 2,
      });
    });

    it("deletes a record and tolerates deleting a missing one", async () => {
      const store = fresh();
      await store.write("a", { v: 1 }, { expiresAt: null });
      await store.delete("a");
      await store.delete("a");
      expect(await store.read("a")).toBeUndefined();
    });

    it("keeps keys independent", async () => {
      const store = fresh();
      await store.write("a", { v: 1 }, { expiresAt: null });
      await store.write("b", { v: 2 }, { expiresAt: null });
      await store.delete("a");
      expect((await store.read("b"))!.value).toEqual({ v: 2 });
    });

    it("stops returning a record once its expiry time is reached", async () => {
      const store = fresh();
      await store.write("a", { v: 1 }, { expiresAt: 2_000 });
      now = 1_999;
      expect(await store.read("a")).toBeDefined();
      now = 2_000;
      expect(await store.read("a")).toBeUndefined();
    });

    it("never expires a record written without an expiry", async () => {
      const store = fresh();
      await store.write("a", { v: 1 }, { expiresAt: null });
      now = 9_999_999_999;
      expect(await store.read("a")).toBeDefined();
    });

    it("treats an expired record as absent for create-only and conditional writes", async () => {
      const store = fresh();
      await store.write("a", { v: 1 }, { expiresAt: 2_000 });
      now = 3_000;
      expect(
        (
          await store.write(
            "a",
            { v: 2 },
            { expiresAt: null, expectedRevision: 1 },
          )
        ).ok,
      ).toBe(false);
      expect(
        await store.write(
          "a",
          { v: 3 },
          { expiresAt: null, expectedRevision: null },
        ),
      ).toEqual({ ok: true, revision: 1 });
    });

    it("refuses an oversized record by bytes and leaves the old one untouched", async () => {
      const store = fresh(4096);
      await store.write("a", { v: "small" }, { expiresAt: null });
      // 2500 Arabic letters are 2500 characters but 5000 bytes.
      const big = { v: "ع".repeat(2500) };
      await expect(
        store.write("a", big, { expiresAt: null }),
      ).rejects.toBeInstanceOf(RecordTooLargeError);
      await expect(
        store.write("b", big, { expiresAt: null, expectedRevision: null }),
      ).rejects.toBeInstanceOf(RecordTooLargeError);
      expect((await store.read("a"))!.value).toEqual({ v: "small" });
      expect(await store.read("b")).toBeUndefined();
    });
  });
}
