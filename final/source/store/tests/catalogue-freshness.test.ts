import { afterEach, expect, it } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { seedProducts } from "../src/catalogue-seed.js";
import { importCatalogue, openCatalogue } from "../src/catalogue-db.js";
import { GuardedCart } from "../src/guarded-cart.js";
import { createApp } from "../src/app.js";
import { browser } from "./browser.js";
const cleanup: (() => void)[] = [];
afterEach(() => {
  for (const fn of cleanup.splice(0).reverse()) fn();
});
function fixture() {
  const dir = mkdtempSync(join(tmpdir(), "copilot-freshness-"));
  cleanup.push(() => rmSync(dir, { recursive: true, force: true }));
  const file = join(dir, "db.sqlite");
  importCatalogue(file, seedProducts);
  const repository = openCatalogue(file);
  cleanup.push(() => repository.close());
  return { file, repository };
}
it("rejects confirmation for a changed price and renders current terms from the same repository", async () => {
  const { file, repository } = fixture();
  const client = await browser(createApp({ evaluation: true, repository }));
  await client.post("/__test/cart").send({
    lines: [{ product_id: "shoe-01", size: "40", color: "blue", quantity: 1 }],
  });
  const old = (await client.get("/cart/state")).body.revision;
  const token = (
    await client
      .post("/__copilot/manual-confirmation")
      .send({ kind: "submit_checkout", cart_revision: old })
  ).body.token;
  importCatalogue(
    file,
    seedProducts.map((p) =>
      p.id === "shoe-01"
        ? { ...p, price: { amount: "99.50", currency: "EGP" } }
        : p,
    ),
  );
  const response = await client.post("/checkout/submit").type("form").send({
    copilot_confirmation: token,
    cart_revision: old,
    card_number: "0000 0000 0000 0000",
    card_expiry: "01/30",
    card_security_code: "000",
  });
  expect(response.status).toBe(403);
  const state = (await client.get("/cart/state")).body;
  expect(state.revision).toBeGreaterThan(old);
  expect(state.orders).toEqual([]);
  expect(state.lines).toHaveLength(1);
  expect((await client.get("/checkout")).text).toContain("99.50");
  expect((await client.get("/p/shoe-01")).text).toContain("99.50");
});
it("keeps order facts immutable and lets obsolete cart lines be removed and undone without extending Undo", () => {
  const { file, repository } = fixture();
  let now = 0;
  const cart = new GuardedCart(() => now, repository);
  cart.edit("add", {
    product_id: "shoe-01",
    size: "40",
    color: "blue",
    quantity: 1,
    revision: 0,
    operation_id: "add",
  });
  const order = cart.submitOrder();
  const unitPrice = cart.state.orders[0].lines[0].unit_price;
  cart.edit("add", {
    product_id: "shoe-01",
    size: "40",
    color: "blue",
    quantity: 1,
    revision: cart.revision,
    operation_id: "again",
  });
  importCatalogue(
    file,
    seedProducts.map((p) =>
      p.id === "shoe-01"
        ? { ...p, available: false, price: { amount: "1", currency: "EGP" } }
        : p,
    ),
  );
  expect(cart.state.orders[0].id).toBe(order);
  expect(cart.state.orders[0].lines[0].unit_price).toEqual(unitPrice);
  expect(() => cart.submitOrder()).toThrow();
  expect(
    cart.edit("remove", {
      product_id: "shoe-01",
      size: "40",
      color: "blue",
      revision: cart.revision,
      operation_id: "remove",
    }),
  ).toBe(true);
  const undo = cart.undo!;
  now = 3000;
  expect(
    cart.edit("undo", {
      undo_id: undo.id,
      revision: cart.revision,
      operation_id: "undo",
    }),
  ).toBe(true);
  expect(() => cart.submitOrder()).toThrow();
  expect(cart.lines).toHaveLength(1);
  expect(cart.undo).toBeNull();
});

it("rejects quantity changes after variant withdrawal while allowing removal", () => {
  const { file, repository } = fixture();
  const cart = new GuardedCart(() => 0, repository);
  const line = { product_id: "shoe-01", size: "40", color: "blue" };
  expect(
    cart.edit("add", {
      ...line,
      quantity: 1,
      revision: 0,
      operation_id: "add",
    }),
  ).toBe(true);
  importCatalogue(
    file,
    seedProducts.map((p) => (p.id === "shoe-01" ? { ...p, sizes: ["41"] } : p)),
  );
  expect(
    cart.edit("quantity", {
      ...line,
      quantity: 2,
      revision: cart.revision,
      operation_id: "change",
    }),
  ).toBe(false);
  expect(cart.lines[0].quantity).toBe(1);
  expect(
    cart.edit("remove", {
      ...line,
      revision: cart.revision,
      operation_id: "remove",
    }),
  ).toBe(true);
});
