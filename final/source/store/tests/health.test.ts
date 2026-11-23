import { browser } from "./browser.js";
import { describe, expect, it } from "vitest";

import { createApp } from "./app.js";

describe("Controlled Storefront", () => {
  it("opens a recommended product by stable ID without relying on search text", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/p/shoe-09");
    expect(response.status).toBe(200);
    expect(response.text).toContain("ممشى النيل");
    expect(response.text).toContain('data-product-id="shoe-09"');
    expect(response.text).not.toContain("لا توجد منتجات مطابقة");
    expect(
      (
        await (
          await browser(createApp({ evaluation: true }))
        ).get("/p/not-a-product")
      ).status,
    ).toBe(404);
  });

  it("exposes an unavailable product as non-purchasable", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/p/shoe-05");

    expect(response.status).toBe(200);
    expect(response.text).toContain("غير متاح");
    expect(response.text).toMatch(/data-testid="add-to-cart"[^>]*disabled/);
  });

  it("refuses an unavailable cart addition at the authoritative Storefront boundary", async () => {
    const app = createApp({ evaluation: true });
    const client = await browser(app);
    const unavailable = await client
      .post("/cart/items")
      .send({ product_id: "shoe-05" });
    const available = await client
      .post("/cart/items")
      .send({ product_id: "shoe-09" });

    expect(unavailable.status).toBe(409);
    expect(unavailable.body).toEqual({ error: "product_unavailable" });
    expect(available.status).toBe(409);
    expect(available.body).toEqual({ error: "invalid_or_stale_cart_edit" });
  });

  it("publishes only versioned public catalogue facts for grounded discovery", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/__catalogue/v1/products");

    expect(response.status).toBe(200);
    expect(response.headers["cache-control"]).toBe("no-store");
    expect(response.body.v).toBe(1);
    expect(response.body.currency).toBe("EGP");
    expect(response.body.products).toHaveLength(60);
    expect(
      response.body.products.find(
        (item: { id: string }) => item.id === "shoe-02",
      ),
    ).toMatchObject({
      price: { amount: "1750", currency: "EGP" },
      suitable_for: ["daily_workouts", "road_running"],
      available: true,
    });
    expect(response.body.products[0]).not.toHaveProperty("cart");
    expect(response.body.products[0]).not.toHaveProperty("payment");
  });
  it("serves an Arabic home page with a shoes category link", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/");

    expect(response.status).toBe(200);
    expect(response.type).toMatch(/html/);
    expect(response.text).toContain('<html lang="ar" dir="rtl">');
    expect(response.text).toContain('href="/c/shoes"');
    expect(response.text).toContain("الأحذية");
  });

  it("provides a cart destination with a link to the fictional checkout page", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/cart");

    expect(response.status).toBe(200);
    expect(response.text).toContain("<h1>السلة</h1>");
    expect(response.text).toContain("السلة فارغة");
    expect(response.text).not.toContain("حذاء تجريبي");
    expect(response.text).toContain('href="/checkout">إتمام الشراء</a>');
    expect(response.text).toContain('href="/account">الحساب</a>');
  });

  it("shows fictional payment fields and keeps order submission unavailable for an empty cart", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/checkout");

    expect(response.status).toBe(200);
    expect(response.text).toContain("<h1>إتمام الشراء</h1>");
    expect(response.text).toContain('autocomplete="cc-number"');
    expect(response.text).toContain('autocomplete="cc-exp"');
    expect(response.text).toContain('autocomplete="cc-csc"');
    expect(response.text).toMatch(/data-testid="place-order"[^>]*disabled/);
    expect(response.text).toContain('action="/checkout/submit"');
  });

  it("links the account page to the configured order-history route", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/account");

    expect(response.status).toBe(200);
    expect(response.text).toContain("<h1>الحساب</h1>");
    expect(response.text).toContain('href="/account/orders">الطلبات</a>');
  });

  it("redirects logged-out order-history visits to user-controlled login", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/account/orders");

    expect(response.status).toBe(302);
    expect(response.headers.location).toBe("/login?next=%2Faccount%2Forders");
  });

  it("returns a safe validation page when login has no form body", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).post("/login");

    expect(response.status).toBe(400);
    expect(response.text).toContain("تسجيل الدخول");
    expect(response.text).not.toContain("undefined");
  });

  it("does not echo a supplied username when login fields are incomplete", async () => {
    const response = await (await browser(createApp({ evaluation: true })))
      .post("/login")
      .type("form")
      .send({ username: "private@example.test" });

    expect(response.status).toBe(400);
    expect(response.text).not.toContain("private@example.test");
  });

  it("authenticates through fictional shopper-entered fields without echoing values", async () => {
    const app = createApp({ evaluation: true });
    const client = await browser(app);
    const login = await client
      .post("/login")
      .type("form")
      .send({ username: "shopper@example.test", password: "fictional-secret" });

    expect(login.status).toBe(303);
    expect(login.headers.location).toBe("/account/orders");
    expect(login.text).not.toContain("shopper@example.test");
    expect(login.text).not.toContain("fictional-secret");
    const orders = await client.get("/account/orders");

    expect(orders.status).toBe(200);
    expect(orders.text).toContain('href="#order-1003">أحدث طلب</a>');
    expect(orders.text).toContain("order-1003");
    expect(orders.text).not.toContain("fictional-secret");
  });

  it("serves a semantic shoes page with deterministic Arabic filters", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/c/shoes");

    expect(response.status).toBe(200);
    expect(response.text).toContain('<form aria-label="فلترة الأحذية"');
    expect(response.text).toContain("<legend>نوع الحذاء</legend>");
    expect(response.text).toContain('name="type" value="running"');
    expect(response.text).toContain('for="max-price">أقصى سعر</label>');
    expect(response.text).toContain("تطبيق الفلاتر");
    expect(response.text).toContain(
      '<script type="module" src="/bridge/runtime.js"></script>',
    );
    expect(response.text.match(/<article /g)).toHaveLength(15);
  });

  it("filters running shoes by an inclusive maximum price in the URL", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/c/shoes?type=running&max_price=2000");

    expect(response.status).toBe(200);
    expect(response.text).toContain("3 منتجات");
    expect(response.text).toContain("عدّاء النيل");
    expect(response.text).not.toContain("ماراثون القاهرة");
    expect(response.text).toContain('value="2000"');
  });

  it("provides a deterministic reset endpoint for isolated Evaluation Cases", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).post("/__test/reset");

    expect(response.status).toBe(204);
    expect(response.text).toBe("");
  });

  it("reports authoritative filtered Storefront state for Evaluation Cases", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/__test/state?type=running&max_price=2000");

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      filters: {
        type: "running",
        min_price: null,
        max_price: { amount: "2000", currency: "EGP" },
      },
      product_ids: ["shoe-01", "shoe-02", "shoe-03"],
      product_count: 3,
    });
  });

  it("reports exact decimal Money in authoritative Storefront state", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/__test/state?category=bags&max_price=1500.50");

    expect(response.status).toBe(200);
    expect(response.body.filters.max_price).toEqual({
      amount: "1500.50",
      currency: "EGP",
    });
  });

  it("serves all four bilingual category links from the home page", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/");

    for (const href of [
      "/c/shoes",
      "/c/clothing",
      "/c/bags",
      "/c/electronics",
    ]) {
      expect(response.text).toContain(`href="${href}"`);
    }
    expect(response.text).toContain("Shoes");
    expect(response.text).toContain("الشنط");
  });

  it("applies generic URL filters and sorting on every category", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get(
      "/c/clothing?q=jacket&type=outerwear&min_price=1000&max_price=1800&size=L&color=black&availability=available&sort=cheapest",
    );

    expect(response.status).toBe(200);
    expect(response.text).toContain("جاكيت القاهرة");
    expect(response.text).toContain('name="q"');
    expect(response.text).toContain('name="availability"');
    expect(response.text).toContain('name="sort"');
    expect(response.text.match(/<article /g)).toHaveLength(1);
  });

  it("reports canonical generic filter state for Evaluation Cases", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get(
      "/__test/state?category=bags&q=Nile&size=M&availability=available&sort=newest",
    );

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      category: "bags",
      filters: {
        q: "Nile",
        type: null,
        min_price: null,
        max_price: null,
        size: "M",
        color: null,
        availability: "available",
        sort: "newest",
      },
      product_ids: ["bag-01"],
      product_count: 1,
    });
  });

  it("renders an explicit empty state without broadening constraints", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/c/shoes?size=99&color=purple&availability=available");

    expect(response.status).toBe(200);
    expect(response.text).toContain("0 منتجات");
    expect(response.text).toContain("لا توجد منتجات مطابقة");
    expect(response.text.match(/<article /g)).toBeNull();
  });

  it("returns not found for an unknown category instead of guessing", async () => {
    const response = await (
      await browser(createApp({ evaluation: true }))
    ).get("/c/toys");

    expect(response.status).toBe(404);
  });
});
