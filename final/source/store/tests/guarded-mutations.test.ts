import { browser } from "./browser.js";
import { describe, expect, it } from "vitest";

import { createApp } from "./app.js";

describe("fictional guarded Storefront mutations", () => {
  it("rejects an unconfirmed bulk clear and consumes one matching confirmation", async () => {
    const app = createApp({ evaluation: true });
    const client = await browser(app);
    const seed = await client
      .post("/__test/cart")
      .send({ lines: [{ product_id: "shoe-09", quantity: 2 }] });
    expect(seed.status).toBe(204);
    const before = await client.get("/__test/cart-state");
    expect(before.body).toMatchObject({
      revision: 1,
      lines: [{ product_id: "shoe-09", quantity: 2 }],
    });
    const noConfirmation = await client
      .post("/cart/clear")
      .type("form")
      .send({ cart_revision: "1" });
    expect(noConfirmation.status).toBe(403);

    const token = (
      await client
        .post("/__copilot/manual-confirmation")
        .send({ kind: "clear_cart", cart_revision: 1 })
    ).body.token;
    const clear = await client
      .post("/cart/clear")
      .type("form")
      .send({ cart_revision: "1", copilot_confirmation: token });
    expect(clear.status).toBe(303);
    expect((await client.get("/__test/cart-state")).body.lines).toEqual([]);
    expect(
      (
        await client.post("/cart/clear").type("form").send({
          cart_revision: "1",
          copilot_confirmation: token,
        })
      ).status,
    ).toBe(403);
  });

  it("submits only a fictional order with Shopper-entered dummy fields and fresh matching confirmation", async () => {
    const app = createApp({ evaluation: true });
    const client = await browser(app);
    await client
      .post("/__test/cart")
      .send({ lines: [{ product_id: "shoe-09", quantity: 1 }] });
    const token = (
      await client
        .post("/__copilot/manual-confirmation")
        .send({ kind: "submit_checkout", cart_revision: 1 })
    ).body.token;
    const noCard = await client.post("/checkout/submit").type("form").send({
      cart_revision: "1",
      copilot_confirmation: token,
    });
    expect(noCard.status).toBe(400);
    expect(noCard.text).toContain("/bridge/runtime.js");
    const reused = await client.post("/checkout/submit").type("form").send({
      cart_revision: "1",
      copilot_confirmation: token,
      card_number: "0000 0000 0000 0000",
      card_expiry: "01/30",
      card_security_code: "000",
    });
    expect(reused.status).toBe(403);
    const fresh = (
      await client
        .post("/__copilot/manual-confirmation")
        .send({ kind: "submit_checkout", cart_revision: 1 })
    ).body.token;
    const submitted = await client.post("/checkout/submit").type("form").send({
      cart_revision: "1",
      copilot_confirmation: fresh,
      card_number: "0000 0000 0000 0000",
      card_expiry: "01/30",
      card_security_code: "000",
    });
    expect(submitted.status).toBe(303);
    expect(submitted.headers.location).toMatch(/^\/order\/complete\//);
    const state = (await client.get("/__test/cart-state")).body;
    expect(state.lines).toEqual([]);
    expect(state.orders).toHaveLength(1);
    expect(JSON.stringify(state)).not.toContain("0000 0000 0000 0000");
  });

  it("rejects an expired or cart-stale confirmation at the mutation endpoint", async () => {
    let now = 1_000;
    const app = createApp({ evaluation: true, clock: () => now });
    const client = await browser(app);
    await client
      .post("/__test/cart")
      .send({ lines: [{ product_id: "shoe-09", quantity: 1 }] });
    const staleToken = (
      await client
        .post("/__copilot/manual-confirmation")
        .send({ kind: "clear_cart", cart_revision: 1 })
    ).body.token;
    await client
      .post("/__test/cart")
      .send({ lines: [{ product_id: "shoe-09", quantity: 2 }] });
    expect(
      (
        await client.post("/cart/clear").type("form").send({
          cart_revision: "1",
          copilot_confirmation: staleToken,
        })
      ).status,
    ).toBe(403);

    const expiringToken = (
      await client
        .post("/__copilot/manual-confirmation")
        .send({ kind: "clear_cart", cart_revision: 2 })
    ).body.token;
    now += 60_000;
    expect(
      (
        await client.post("/cart/clear").type("form").send({
          cart_revision: "2",
          copilot_confirmation: expiringToken,
        })
      ).status,
    ).toBe(403);
    expect((await client.get("/__test/cart-state")).body.lines).toEqual([
      { product_id: "shoe-09", quantity: 2 },
    ]);
  });
});
