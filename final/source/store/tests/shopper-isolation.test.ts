import request from "supertest";
import { describe, expect, it } from "vitest";
import { createApp } from "./app.js";
import { browser } from "./browser.js";

describe("independent shoppers", () => {
  it("keeps equal-revision carts and Undo authority separate", async () => {
    const app = createApp();
    const a = request.agent(app),
      b = request.agent(app);
    const bootA = await a.get("/__shopper");
    const bootB = await b.get("/__shopper");
    const item = { product_id: "shoe-09", size: "43", color: "blue" };
    const added = await a
      .post("/cart/items")
      .set("Origin", "http://localhost:4000")
      .set("x-csrf-token", bootA.body.csrf ?? "")
      .send({ ...item, quantity: 1, revision: 0, operation_id: "a" });
    expect(added.status).toBe(200);
    expect((await b.get("/cart/state")).body.lines).toEqual([]);
    const other = await b
      .post("/cart/items")
      .set("Origin", "http://localhost:4000")
      .set("x-csrf-token", bootB.body.csrf ?? "")
      .send({ ...item, quantity: 3, revision: 0, operation_id: "b" });
    expect(other.status).toBe(200);
    expect(
      (
        await b
          .post("/cart/undo")
          .set("Origin", "http://localhost:4000")
          .set("x-csrf-token", bootB.body.csrf ?? "")
          .send({
            revision: 1,
            operation_id: "steal",
            undo_id: added.body.undo.id,
          })
      ).status,
    ).toBe(409);
    expect((await a.get("/cart/state")).body.lines[0].quantity).toBe(1);
    expect((await b.get("/cart/state")).body.lines[0].quantity).toBe(3);
  });
  it("rejects unauthenticated writes and disables test routes by default", async () => {
    const app = createApp();
    expect((await request(app).post("/cart/items").send({})).status).toBe(401);
    expect((await request(app).post("/__test/reset")).status).toBe(404);
    const a = await browser(app);
    expect((await a.post("/__TEST/reset")).status).toBe(404);
  });
  it("keeps confirmations, fictional login and completed orders with their owner", async () => {
    const app = createApp({ evaluation: true });
    const a = await browser(app),
      b = await browser(app);
    for (const client of [a, b])
      await client
        .post("/__test/cart")
        .send({ lines: [{ product_id: "shoe-09", quantity: 1 }] });
    const token = (
      await a
        .post("/__copilot/manual-confirmation")
        .send({ kind: "submit_checkout", cart_revision: 1 })
    ).body.token;
    const body = {
      cart_revision: "1",
      copilot_confirmation: token,
      card_number: "0000 0000 0000 0000",
      card_expiry: "01/30",
      card_security_code: "000",
    };
    expect(
      (await b.post("/checkout/submit").type("form").send(body)).status,
    ).toBe(403);
    const result = await a.post("/checkout/submit").type("form").send(body);
    expect(result.status).toBe(303);
    expect((await a.get(result.headers.location)).status).toBe(200);
    expect((await b.get(result.headers.location)).status).toBe(404);
    await a
      .post("/login")
      .type("form")
      .send({ username: "demo", password: "fictional" });
    expect((await a.get("/account/orders")).status).toBe(200);
    expect((await a.get("/account/orders")).text).toContain(
      `href="${result.headers.location}">أحدث طلب</a>`,
    );
    expect((await b.get("/account/orders")).status).toBe(302);
    expect((await b.get("/cart/state")).body.lines).toHaveLength(1);
    expect((await a.get("/cart/state")).headers["cache-control"]).toBe(
      "no-store",
    );
  });
  it("rejects forged, cross-origin and missing-CSRF writes without changing the cart", async () => {
    const app = createApp();
    const a = await browser(app);
    const body = {
      product_id: "shoe-09",
      size: "43",
      color: "blue",
      quantity: 1,
      revision: 0,
      operation_id: "x",
    };
    expect(
      (
        await a
          .post("/cart/items")
          .set("Origin", "https://hostile.example")
          .send(body)
      ).status,
    ).toBe(403);
    expect(
      (await a.post("/cart/items").set("x-csrf-token", "").send(body)).status,
    ).toBe(403);
    expect(
      (
        await request(app)
          .get("/cart/state")
          .set("Cookie", "copilot_store=forged")
      ).status,
    ).toBe(401);
    expect((await a.get("/cart/state")).body.lines).toEqual([]);
  });
  it("rejects capacity overflow and expires inactive shoppers without silently accepting old writes", async () => {
    let now = 0;
    const app = createApp({ clock: () => now, capacity: 1, ttlMs: 100 });
    const a = await browser(app);
    expect((await request(app).get("/__shopper")).status).toBe(503);
    now = 100;
    expect((await a.post("/cart/items").send({})).status).toBe(401);
    expect((await request(app).get("/__shopper")).status).toBe(200);
  });
});
