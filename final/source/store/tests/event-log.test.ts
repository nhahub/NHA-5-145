import { browser } from "./browser.js";
import { describe, expect, it } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createApp as createRawApp } from "../src/app.js";
import { importCatalogue, openCatalogue } from "../src/catalogue-db.js";
import { seedProducts } from "../src/catalogue-seed.js";
import { createApp } from "./app.js";
import { memorySink, StoreEventLog } from "../src/event-log.js";

const item = { product_id: "shoe-09", size: "43", color: "blue", quantity: 1 };
const RECORD_KEYS = new Set([
  "time",
  "release",
  "event",
  "change",
  "outcome",
  "status",
  "error_type",
  "route",
]);

function logged() {
  const sink = memorySink();
  return { sink, events: new StoreEventLog(sink, "test-release") };
}

async function confirmation(
  client: Awaited<ReturnType<typeof browser>>,
  kind: string,
  revision: number,
) {
  return (
    await client
      .post("/__copilot/manual-confirmation")
      .send({ kind, cart_revision: revision })
  ).body.token as string;
}

describe("Storefront event log", () => {
  it("records each cart change once by type and outcome", async () => {
    const { sink, events } = logged();
    const client = await browser(createApp({ evaluation: true, events }));

    const add = await client
      .post("/cart/items")
      .send({ ...item, revision: 0, operation_id: "a" });
    await client
      .post("/cart/quantity")
      .send({ ...item, quantity: 2, revision: 1, operation_id: "q" });
    await client
      .post("/cart/remove")
      .send({ ...item, quantity: 2, revision: 2, operation_id: "r" });
    await client.post("/cart/undo").send({
      revision: 3,
      operation_id: "u",
      undo_id: (await client.get("/cart/state")).body.undo.id,
    });
    await client
      .post("/cart/clear")
      .type("form")
      .send({
        cart_revision: "4",
        copilot_confirmation: await confirmation(client, "clear_cart", 4),
      });
    await client
      .post("/cart/items")
      .send({ ...item, revision: 5, operation_id: "a2" });
    await client
      .post("/checkout/submit")
      .type("form")
      .send({
        cart_revision: "6",
        copilot_confirmation: await confirmation(client, "submit_checkout", 6),
        card_number: "0000 0000 0000 0000",
        card_expiry: "01/30",
        card_security_code: "000",
      });

    expect(add.status).toBe(200);
    expect(
      sink.records.map((r) => [r.event, r.change, r.outcome, r.status]),
    ).toEqual([
      ["cart_change", "add", "ok", 200],
      ["cart_change", "quantity", "ok", 200],
      ["cart_change", "remove", "ok", 200],
      ["cart_change", "undo", "ok", 200],
      ["cart_change", "clear", "ok", 303],
      ["cart_change", "add", "ok", 200],
      ["cart_change", "checkout", "ok", 303],
    ]);
    expect(sink.records.every((r) => r.release === "test-release")).toBe(true);
    expect(
      sink.records.every(
        (r) => typeof r.time === "string" && !Number.isNaN(Date.parse(r.time)),
      ),
    ).toBe(true);
  });

  it("records refused cart changes with the reason", async () => {
    const { sink, events } = logged();
    const client = await browser(createApp({ evaluation: true, events }));

    await client
      .post("/cart/items")
      .send({ ...item, product_id: "nope", revision: 0, operation_id: "x" });
    await client
      .post("/cart/items")
      .send({ ...item, product_id: "shoe-05", revision: 0, operation_id: "y" });
    await client
      .post("/cart/quantity")
      .send({ ...item, revision: 7, operation_id: "z" });
    await client.post("/cart/clear").type("form").send({ cart_revision: "0" });
    await client
      .post("/__test/cart")
      .send({ lines: [{ product_id: "shoe-09", quantity: 1 }] });
    await client
      .post("/checkout/submit")
      .type("form")
      .send({
        cart_revision: "1",
        copilot_confirmation: await confirmation(client, "submit_checkout", 1),
      });

    expect(sink.records.map((r) => [r.change, r.outcome, r.status])).toEqual([
      ["add", "unknown_product", 404],
      ["add", "unavailable", 409],
      ["quantity", "rejected", 409],
      ["clear", "unconfirmed", 403],
      ["checkout", "invalid_payment", 400],
    ]);
  });

  it("never records the product, size, colour, quantity or payment fields", async () => {
    const { sink, events } = logged();
    const client = await browser(createApp({ evaluation: true, events }));
    await client
      .post("/cart/items")
      .send({ ...item, quantity: 7, revision: 0, operation_id: "a" });
    await client
      .post("/checkout/submit")
      .type("form")
      .send({
        cart_revision: "1",
        copilot_confirmation: await confirmation(client, "submit_checkout", 1),
        card_number: "4111 1111 1111 1111",
      });

    const text = sink.lines.join("\n");
    for (const value of ["shoe-09", "blue", "4111", '"quantity"', "size"])
      expect(text).not.toContain(value);
    for (const record of sink.records)
      for (const key of Object.keys(record)) expect(RECORD_KEYS).toContain(key);
  });

  it("records an unexpected error by type and route, without its message", async () => {
    const { sink, events } = logged();
    const directory = mkdtempSync(join(tmpdir(), "copilot-log-db-"));
    const file = join(directory, "catalogue.sqlite");
    importCatalogue(file, seedProducts);
    const real = openCatalogue(file);
    const broken = new Proxy(real, {
      get(target, property) {
        if (property === "get")
          return () => {
            throw new RangeError("secret shoe-09 details");
          };
        const value = Reflect.get(target, property, target);
        return typeof value === "function" ? value.bind(target) : value;
      },
    });
    try {
      const client = await browser(
        createRawApp({ repository: broken, evaluation: true, events }),
      );
      const response = await client
        .post("/cart/items")
        .send({ ...item, revision: 0, operation_id: "a" });

      expect(response.status).toBe(500);
      expect(sink.records).toEqual([
        expect.objectContaining({
          event: "error",
          error_type: "RangeError",
          route: "/cart/items",
        }),
      ]);
      expect(sink.lines.join("\n")).not.toContain("secret");
    } finally {
      real.close();
      rmSync(directory, { recursive: true, force: true });
    }
  });

  it("does not record a shopper's malformed request as a server error", async () => {
    const { sink, events } = logged();
    const client = await browser(createApp({ evaluation: true, events }));

    const response = await client
      .post("/cart/items")
      .set("Content-Type", "application/json")
      .send("{not json");

    expect(response.status).toBe(400);
    expect(sink.records).toEqual([]);
  });

  it("keeps serving the cart when the log cannot be written", async () => {
    const events = new StoreEventLog({
      write() {
        throw new Error("disk full");
      },
    });
    const client = await browser(createApp({ evaluation: true, events }));

    const add = await client
      .post("/cart/items")
      .send({ ...item, revision: 0, operation_id: "a" });

    expect(add.status).toBe(200);
    expect(events.failures).toBe(1);
  });

  it("refuses a record with a value outside its allow-list", () => {
    const { sink, events } = logged();

    events.cartChange("add", "ok", 200);
    // Simulates a future caller passing free text where a fixed value belongs.
    events.cartChange("shoe-09 blue" as never, "ok", 200);
    events.error(Object.assign(new Error("x"), { name: "عايز كوتشي" }));

    expect(sink.records.map((r) => r.change ?? r.error_type)).toEqual([
      "add",
      "Error",
    ]);
  });
});
