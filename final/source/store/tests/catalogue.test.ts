import { seedProducts as products } from "../src/catalogue-seed.js";
import { describe, expect, it } from "vitest";

import {
  categories,
  compareMoney,
  filterProductRecords,
  money,
} from "../src/catalogue.js";

describe("deterministic bilingual catalogue", () => {
  it("contains sixty products across four categories with discovery attributes", () => {
    expect(products).toHaveLength(60);
    expect(categories).toEqual(["shoes", "clothing", "bags", "electronics"]);
    expect(new Set(products.map((product) => product.category))).toEqual(
      new Set(categories),
    );
    for (const category of categories) {
      expect(
        products.filter((product) => product.category === category),
      ).toHaveLength(15);
    }
    for (const product of products) {
      expect(product.nameAr.length).toBeGreaterThan(0);
      expect(product.nameEn.length).toBeGreaterThan(0);
      expect(product.type.length).toBeGreaterThan(0);
      expect(product.sizes.length).toBeGreaterThan(0);
      expect(product.colors.length).toBeGreaterThan(0);
      expect(product.addedAt).toMatch(/^2026-\d{2}-\d{2}$/);
    }
    expect(new Set(products.map((product) => product.available))).toEqual(
      new Set([true, false]),
    );
  });

  it("preserves the tracer's first three available running shoes at or below EGP 2000", () => {
    expect(
      filterProductRecords(products, {
        category: "shoes",
        type: "running",
        maxPrice: money("2000"),
      }).map((product) => product.id),
    ).toEqual(["shoe-01", "shoe-02", "shoe-03"]);
  });

  it("combines type, inclusive prices, size, color, and availability", () => {
    expect(
      filterProductRecords(products, {
        category: "clothing",
        type: "outerwear",
        minPrice: money("1000"),
        maxPrice: money("1800"),
        size: "L",
        color: "black",
        availability: true,
      }).map((product) => product.id),
    ).toEqual(["clothing-01"]);
  });

  it("searches Arabic and English product text without changing the category", () => {
    expect(
      filterProductRecords(products, { category: "bags", query: "Nile" }).map(
        (product) => product.id,
      ),
    ).toEqual(["bag-01"]);
    expect(
      filterProductRecords(products, {
        category: "electronics",
        query: "النيل",
      }).map((product) => product.id),
    ).toEqual(["electronics-01"]);
  });

  it("does not return other clothing for a brown shirt request", () => {
    expect(
      filterProductRecords(products, {
        category: "clothing",
        type: "shirts",
        color: "brown",
      }),
    ).toEqual([]);
  });

  it("sorts matching products by cheapest with stable id tie-breaking", () => {
    const result = filterProductRecords(products, {
      category: "bags",
      sort: "cheapest",
    });

    expect(result.map((product) => product.price.amount)).toEqual(
      [...result]
        .map((product) => product.price)
        .sort(compareMoney)
        .map((price) => price.amount),
    );
    expect(result[0]?.id).toBe("bag-06");
  });

  it("sorts matching products by newest with stable id tie-breaking", () => {
    const result = filterProductRecords(products, {
      category: "electronics",
      sort: "newest",
    });

    expect(result.slice(0, 3).map((product) => product.id)).toEqual([
      "electronics-15",
      "electronics-14",
      "electronics-13",
    ]);
  });

  it("keeps a valid zero-result query empty", () => {
    expect(
      filterProductRecords(products, {
        category: "shoes",
        size: "99",
        color: "purple",
        availability: true,
      }),
    ).toEqual([]);
  });

  it("represents catalogue prices and decimal constraints as exact EGP Money", () => {
    expect(products[0]?.price).toEqual({ amount: "1450", currency: "EGP" });
    expect(compareMoney(money("0.10"), money("0.2"))).toBeLessThan(0);
    expect(() => money("1.234")).toThrow(/decimal/);
  });
});
