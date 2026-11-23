import request from "supertest";
import { afterEach, describe, expect, it } from "vitest";
import { DatabaseSync } from "node:sqlite";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createApp } from "./app.js";
import { memorySink, StoreEventLog } from "../src/event-log.js";
import {
  SqliteShopperStateStore,
  type ShopperStateStore,
  type WriteOptions,
} from "../src/shopper-state-store.js";

const secret = "test-only-service-credential-not-a-real-secret";
const origin = "http://localhost:4000";
const audience = "http://localhost:4100";
const item = { product_id: "shoe-09", size: "43", color: "blue", quantity: 1 };
const DAY = 24 * 60 * 60 * 1000;

const cleanups: (() => void)[] = [];
afterEach(() => {
  for (const done of cleanups.splice(0)) done();
});

/** A throwaway state file; each `open` is one "process" using it. */
function stateFile(options: { maxRecordBytes?: number } = {}) {
  const directory = mkdtempSync(join(tmpdir(), "copilot-restart-"));
  const path = join(directory, "storefront-state.sqlite");
  const stores: SqliteShopperStateStore[] = [];
  cleanups.push(() => {
    for (const store of stores) store.close();
    rmSync(directory, { recursive: true, force: true });
  });
  return {
    path,
    open(clock?: () => number) {
      const store = new SqliteShopperStateStore(path, { clock, ...options });
      stores.push(store);
      return store;
    },
  };
}

type Session = { cookie: string; csrf: string };

/** Real cookie/CSRF bootstrap against one app instance. */
async function signIn(app: ReturnType<typeof createApp>): Promise<Session> {
  const response = await request(app).get("/__shopper");
  expect(response.status).toBe(200);
  return {
    cookie: String(response.headers["set-cookie"][0]).split(";")[0],
    csrf: response.body.csrf,
  };
}

/** The same browser (cookie + CSRF) talking to whichever instance is running. */
function tab(app: ReturnType<typeof createApp>, session: Session) {
  const agent = request.agent(app);
  agent.set("Cookie", session.cookie);
  agent.set("Origin", origin);
  agent.set("x-csrf-token", session.csrf);
  return agent;
}

async function checkout(client: ReturnType<typeof tab>, revision: number) {
  const token = (
    await client
      .post("/__copilot/manual-confirmation")
      .send({ kind: "submit_checkout", cart_revision: revision })
  ).body.token;
  return client
    .post("/checkout/submit")
    .type("form")
    .send({
      cart_revision: String(revision),
      copilot_confirmation: token,
      card_number: "0000 0000 0000 0000",
      card_expiry: "01/30",
      card_security_code: "000",
    });
}

describe("Shopper state survives a Storefront restart", () => {
  it("keeps cart lines, quantities, revision, orders and sign-in", async () => {
    const file = stateFile();
    const first = createApp({ evaluation: true, stateStore: file.open() });
    const session = await signIn(first);
    const one = tab(first, session);
    await one
      .post("/cart/items")
      .send({ ...item, revision: 0, operation_id: "add-1" });
    await one
      .post("/cart/quantity")
      .send({ ...item, quantity: 3, revision: 1, operation_id: "q-1" });
    const placed = await checkout(one, 2);
    expect(placed.status).toBe(303);
    const orderPath = String(placed.headers.location);
    await one
      .post("/cart/items")
      .send({ ...item, quantity: 2, revision: 3, operation_id: "add-2" });
    await one.post("/login").type("form").send({
      username: "a",
      password: "b",
      copilot_csrf: session.csrf,
    });
    const before = (await one.get("/cart/state")).body;
    expect(before.lines).toEqual([{ ...item, quantity: 2 }]);
    expect(before.orders).toHaveLength(1);

    const second = createApp({ evaluation: true, stateStore: file.open() });
    const two = tab(second, session);
    const after = (await two.get("/cart/state")).body;
    expect(after.lines).toEqual(before.lines);
    expect(after.revision).toBe(before.revision);
    expect(after.orders).toEqual(before.orders);
    expect(after.shopper_context).toBe(before.shopper_context);
    expect((await two.get(orderPath)).status).toBe(200);
    // Signed in: the order history opens instead of redirecting to the login page.
    expect((await two.get("/account/orders")).status).toBe(200);
  });

  it("keeps the Agent's Shopper link valid (binding and generation)", async () => {
    const file = stateFile();
    const first = createApp({
      evaluation: true,
      serviceSecret: secret,
      stateStore: file.open(),
    });
    const session = await signIn(first);
    const challenge = "a".repeat(64);
    const issued = await tab(first, session)
      .post("/__copilot/link-ticket")
      .send({ challenge, audience });
    const redeemed = await request(first)
      .post("/__internal/link/redeem")
      .set("x-service-secret", secret)
      .send({ ticket: issued.body.ticket, challenge, audience });
    expect(redeemed.status).toBe(200);

    const second = createApp({
      evaluation: true,
      serviceSecret: secret,
      stateStore: file.open(),
    });
    expect(
      (
        await request(second)
          .post("/__internal/shopper/validate")
          .set("x-service-secret", secret)
          .send(redeemed.body)
      ).status,
    ).toBe(200);
    // A fresh process, a fresh generation is never invented: a wrong one stays refused.
    expect(
      (
        await request(second)
          .post("/__internal/shopper/validate")
          .set("x-service-secret", secret)
          .send({ ...redeemed.body, generation: "f".repeat(64) })
      ).status,
    ).toBe(410);
    // A link ticket is a one-minute handshake and is not stored: after a restart the
    // Panel simply asks for a new one (the old ticket is refused).
    expect(
      (
        await request(second)
          .post("/__internal/link/redeem")
          .set("x-service-secret", secret)
          .send({ ticket: issued.body.ticket, challenge, audience })
      ).status,
    ).toBe(409);
    const fresh = await tab(second, session)
      .post("/__copilot/link-ticket")
      .send({ challenge, audience });
    const again = await request(second)
      .post("/__internal/link/redeem")
      .set("x-service-secret", secret)
      .send({ ticket: fresh.body.ticket, challenge, audience });
    expect(again.body).toEqual(redeemed.body);
  });

  it("still refuses a replayed operation id", async () => {
    const file = stateFile();
    const first = createApp({ evaluation: true, stateStore: file.open() });
    const session = await signIn(first);
    const added = await tab(first, session)
      .post("/cart/items")
      .send({ ...item, revision: 0, operation_id: "once" });
    expect(added.status).toBe(200);
    const second = createApp({ evaluation: true, stateStore: file.open() });
    const replay = await tab(second, session)
      .post("/cart/quantity")
      .send({ ...item, quantity: 2, revision: 1, operation_id: "once" });
    expect(replay.status).toBe(409);
    expect((await tab(second, session).get("/cart/state")).body.lines).toEqual([
      item,
    ]);
  });

  it("ends the Undo window and open Confirmations at a restart", async () => {
    const file = stateFile();
    const first = createApp({ evaluation: true, stateStore: file.open() });
    const session = await signIn(first);
    const one = tab(first, session);
    await one.post("/__test/cart").send({ lines: [{ ...item }] });
    const added = await one
      .post("/cart/quantity")
      .send({ ...item, quantity: 2, revision: 1, operation_id: "q" });
    expect(added.body.undo).not.toBeNull();
    const token = (
      await one
        .post("/__copilot/manual-confirmation")
        .send({ kind: "clear_cart", cart_revision: 2 })
    ).body.token;

    const second = createApp({ evaluation: true, stateStore: file.open() });
    const two = tab(second, session);
    const state = (await two.get("/cart/state")).body;
    expect(state.undo).toBeNull();
    expect(state.lines).toEqual([{ ...item, quantity: 2 }]);
    const refused = await two
      .post("/cart/clear")
      .type("form")
      .send({ cart_revision: "2", copilot_confirmation: token });
    expect(refused.status).toBe(403);
    expect((await two.get("/cart/state")).body.lines).toHaveLength(1);
    // A new Confirmation works as usual.
    const fresh = (
      await two
        .post("/__copilot/manual-confirmation")
        .send({ kind: "clear_cart", cart_revision: 2 })
    ).body.token;
    expect(
      (
        await two
          .post("/cart/clear")
          .type("form")
          .send({ cart_revision: "2", copilot_confirmation: fresh })
      ).status,
    ).toBe(303);
  });

  it("keeps only the newest orders", async () => {
    const file = stateFile();
    const first = createApp({ evaluation: true, stateStore: file.open() });
    const session = await signIn(first);
    const one = tab(first, session);
    const ids: string[] = [];
    let revision = 0;
    for (let index = 0; index < 22; index++) {
      await one.post("/__test/cart").send({ lines: [{ ...item }] });
      revision = (await one.get("/cart/state")).body.revision;
      const placed = await checkout(one, revision);
      expect(placed.status).toBe(303);
      ids.push(String(placed.headers.location).split("/").pop()!);
    }
    const second = createApp({ evaluation: true, stateStore: file.open() });
    const orders = (await tab(second, session).get("/cart/state")).body.orders;
    expect(orders.map((order: { id: string }) => order.id)).toEqual(
      ids.slice(-20),
    );
  });

  it("emits the same content-free event records", async () => {
    const file = stateFile();
    const sink = memorySink();
    const events = new StoreEventLog(sink, "test");
    const first = createApp({
      evaluation: true,
      stateStore: file.open(),
      events,
    });
    const session = await signIn(first);
    await tab(first, session)
      .post("/cart/items")
      .send({ ...item, revision: 0, operation_id: "a" });
    const second = createApp({
      evaluation: true,
      stateStore: file.open(),
      events,
    });
    await tab(second, session)
      .post("/cart/quantity")
      .send({ ...item, quantity: 2, revision: 1, operation_id: "b" });
    const records = sink.records;
    expect(records.length).toBeGreaterThanOrEqual(2);
    const allowed = new Set([
      "time",
      "release",
      "event",
      "change",
      "outcome",
      "status",
      "error_type",
      "route",
    ]);
    for (const record of records)
      for (const key of Object.keys(record))
        expect(allowed.has(key)).toBe(true);
    expect(JSON.stringify(records)).not.toContain("shoe-09");
  });
});

describe("Shopper state lifetime and secrecy", () => {
  it("expires seven days after the last activity, and activity extends it", async () => {
    let now = 1_000_000;
    const file = stateFile();
    const clock = () => now;
    const first = createApp({
      evaluation: true,
      clock,
      stateStore: file.open(clock),
    });
    const session = await signIn(first);
    await tab(first, session)
      .post("/__test/cart")
      .send({ lines: [{ ...item }] });
    now += 6 * DAY;
    // A restart six days later: still there, and this visit restarts the clock.
    const second = createApp({
      evaluation: true,
      clock,
      stateStore: file.open(clock),
    });
    expect(
      (await tab(second, session).get("/cart/state")).body.lines,
    ).toHaveLength(1);
    now += 6 * DAY;
    const third = createApp({
      evaluation: true,
      clock,
      stateStore: file.open(clock),
    });
    expect((await tab(third, session).get("/cart/state")).status).toBe(200);
    now += 7 * DAY;
    const fourth = createApp({
      evaluation: true,
      clock,
      stateStore: file.open(clock),
    });
    expect((await tab(fourth, session).get("/cart/state")).status).toBe(401);
  });

  it("stores only a digest of the credential", async () => {
    const file = stateFile();
    const app = createApp({ evaluation: true, stateStore: file.open() });
    const session = await signIn(app);
    await tab(app, session)
      .post("/__test/cart")
      .send({ lines: [{ ...item }] });
    const credential = session.cookie.split("=")[1];
    expect(credential).toHaveLength(64);
    const database = new DatabaseSync(file.path, { readOnly: true });
    try {
      const rows = database
        .prepare("SELECT key, value FROM shopper_state")
        .all();
      expect(rows.length).toBeGreaterThanOrEqual(3);
      for (const row of rows) {
        expect(String(row.key)).not.toContain(credential);
        expect(String(row.value)).not.toContain(credential);
      }
    } finally {
      database.close();
    }
  });
});

/** Wraps a real store so a test can break or race its writes. */
class FlakyStore implements ShopperStateStore {
  failWrites = false;
  alwaysConflict = false;
  /** When set, the first two conditional Shopper writes wait for each other. */
  barrier = false;
  #waiting: (() => void) | undefined;
  constructor(readonly inner: ShopperStateStore) {}
  read(key: string) {
    return this.inner.read(key);
  }
  async write(key: string, value: unknown, options: WriteOptions) {
    if (this.failWrites) throw new Error("disk full");
    const conditional =
      key.startsWith("storefront:shopper:") &&
      typeof options.expectedRevision === "number";
    if (conditional && this.alwaysConflict) return { ok: false as const };
    if (conditional && this.barrier) {
      if (this.#waiting) {
        this.#waiting();
        this.#waiting = undefined;
        this.barrier = false;
      } else {
        await new Promise<void>((release) => {
          this.#waiting = release;
        });
      }
    }
    return this.inner.write(key, value, options);
  }
  delete(key: string) {
    return this.inner.delete(key);
  }
}

describe("Shopper state writes", () => {
  it("does not write on a read-only request, only when activity is old enough to matter", async () => {
    let now = 1_000_000;
    const clock = () => now;
    const file = stateFile();
    const inner = file.open(clock);
    let writes = 0;
    const counting: ShopperStateStore = {
      read: (key) => inner.read(key),
      write: (key, value, options) => {
        writes++;
        return inner.write(key, value, options);
      },
      delete: (key) => inner.delete(key),
    };
    const app = createApp({ evaluation: true, clock, stateStore: counting });
    const session = await signIn(app);
    await tab(app, session)
      .post("/cart/items")
      .send({ ...item, revision: 0, operation_id: "w-1" });
    const client = tab(app, session);
    writes = 0;
    now += 1000;
    expect((await client.get("/cart/state")).status).toBe(200);
    expect((await client.get("/cart/state")).status).toBe(200);
    expect(writes).toBe(0);
    // An hour later the new activity time is saved, so the lifetime still extends.
    now += 60 * 60 * 1000;
    expect((await client.get("/cart/state")).status).toBe(200);
    expect(writes).toBeGreaterThan(0);
  });
});

describe("Shopper state saves fail visibly", () => {
  it("fails the request when the save fails, and the change never lands", async () => {
    const file = stateFile();
    const flaky = new FlakyStore(file.open());
    const app = createApp({ evaluation: true, stateStore: flaky });
    const session = await signIn(app);
    flaky.failWrites = true;
    const failed = await tab(app, session)
      .post("/cart/items")
      .send({ ...item, revision: 0, operation_id: "x" });
    expect(failed.status).toBe(503);
    expect(failed.body).toEqual({ error: "shopper_state_unavailable" });
    flaky.failWrites = false;
    const state = (await tab(app, session).get("/cart/state")).body;
    expect(state.lines).toEqual([]);
    expect(state.revision).toBe(0);
  });

  it("fails the request when the record is too large", async () => {
    const file = stateFile({ maxRecordBytes: 1500 });
    const app = createApp({ evaluation: true, stateStore: file.open() });
    const session = await signIn(app);
    const one = tab(app, session);
    let failed: request.Response | undefined;
    let revision = 0;
    for (let index = 0; index < 30 && !failed; index++) {
      const response = await one.post("/cart/items").send({
        ...item,
        revision,
        operation_id: String(index).padEnd(100, "x"),
      });
      if (response.status === 200) revision++;
      else failed = response;
    }
    expect(failed?.status).toBe(503);
    expect(failed?.body).toEqual({ error: "shopper_state_unavailable" });
    // The refused change is not in the Shopper's cart.
    const state = (await one.get("/cart/state")).body;
    expect(state.revision).toBe(revision);
  });

  it("never loses an update when two tabs race: the loser reloads and retries once", async () => {
    const file = stateFile();
    const flaky = new FlakyStore(file.open());
    const app = createApp({ evaluation: true, stateStore: flaky });
    const session = await signIn(app);
    flaky.barrier = true;
    const [added, signedIn] = await Promise.all([
      tab(app, session)
        .post("/cart/items")
        .send({ ...item, revision: 0, operation_id: "race-add" }),
      tab(app, session)
        .post("/login")
        .type("form")
        .send({ username: "a", password: "b", copilot_csrf: session.csrf }),
    ]);
    expect(added.status).toBe(200);
    expect(signedIn.status).toBe(303);
    const state = (await tab(app, session).get("/cart/state")).body;
    expect(state.lines).toEqual([item]);
    expect((await tab(app, session).get("/account/orders")).status).toBe(200);
  });

  it("answers a stale racing edit with the normal stale-edit refusal, never a lost cart", async () => {
    const file = stateFile();
    const flaky = new FlakyStore(file.open());
    const app = createApp({ evaluation: true, stateStore: flaky });
    const session = await signIn(app);
    flaky.barrier = true;
    const results = await Promise.all(
      ["race-a", "race-b"].map((id) =>
        tab(app, session)
          .post("/cart/items")
          .send({ ...item, revision: 0, operation_id: id }),
      ),
    );
    expect(results.map((r) => r.status).sort()).toEqual([200, 409]);
    expect((await tab(app, session).get("/cart/state")).body.lines).toEqual([
      item,
    ]);
  });

  it("fails visibly when the retry also loses the race", async () => {
    const file = stateFile();
    const flaky = new FlakyStore(file.open());
    const app = createApp({ evaluation: true, stateStore: flaky });
    const session = await signIn(app);
    flaky.alwaysConflict = true;
    const response = await tab(app, session)
      .post("/cart/items")
      .send({ ...item, revision: 0, operation_id: "x" });
    expect(response.status).toBe(409);
    expect(response.body).toEqual({ error: "shopper_state_conflict" });
    flaky.alwaysConflict = false;
    expect((await tab(app, session).get("/cart/state")).body.lines).toEqual([]);
  });

  it("logs a failed save as rejected with the status the Shopper received, never ok", async () => {
    const file = stateFile();
    const flaky = new FlakyStore(file.open());
    const sink = memorySink();
    const events = new StoreEventLog(sink, "test");
    const app = createApp({ evaluation: true, stateStore: flaky, events });
    const session = await signIn(app);
    flaky.failWrites = true;
    const failed = await tab(app, session)
      .post("/cart/items")
      .send({ ...item, revision: 0, operation_id: "x" });
    expect(failed.status).toBe(503);
    expect(sink.records).toMatchObject([
      { event: "cart_change", change: "add", outcome: "rejected", status: 503 },
    ]);
    flaky.failWrites = false;
    flaky.alwaysConflict = true;
    const lost = await tab(app, session)
      .post("/cart/items")
      .send({ ...item, revision: 0, operation_id: "y" });
    expect(lost.status).toBe(409);
    expect(sink.records.slice(1)).toMatchObject([
      { change: "add", outcome: "rejected", status: 409 },
    ]);
    flaky.alwaysConflict = false;
    const ok = await tab(app, session)
      .post("/cart/items")
      .send({ ...item, revision: 0, operation_id: "z" });
    expect(ok.status).toBe(200);
    expect(sink.records.slice(2)).toMatchObject([
      { change: "add", outcome: "ok", status: 200 },
    ]);
  });
});
