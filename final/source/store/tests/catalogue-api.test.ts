import { readFileSync } from "node:fs";
import { parseSearch } from "../src/catalogue-query.js";
import type { ProductEvidence } from "../src/product-repository.js";
import { expect, it } from "vitest";
import request from "supertest";
import { createApp } from "./app.js";

const secret = "test-catalogue-service-secret-only";
const query = {
  v: 1,
  query: "",
  predicates: [],
  requirements: [],
  unverified_requirements: [],
  sort: "relevance",
  cursor: null,
};
it("requires service authority and filters the whole catalogue before bounded pagination", async () => {
  const app = createApp({ serviceSecret: secret });
  expect(
    (await request(app).post("/__internal/catalogue/search").send(query))
      .status,
  ).toBe(403);
  const first = await request(app)
    .post("/__internal/catalogue/search")
    .set("x-service-secret", secret)
    .send(query);
  expect(first.status).toBe(200);
  expect(first.body.candidates).toHaveLength(10);
  expect(first.body.next_cursor).toBeTypeOf("string");
  const second = await request(app)
    .post("/__internal/catalogue/search")
    .set("x-service-secret", secret)
    .send({ ...query, cursor: first.body.next_cursor });
  expect(second.status).toBe(200);
  expect(
    new Set(
      [...first.body.candidates, ...second.body.candidates].map(
        (c) => c.product.id,
      ),
    ).size,
  ).toBe(20);
  const filtered = await request(app)
    .post("/__internal/catalogue/search")
    .set("x-service-secret", secret)
    .send({
      ...query,
      predicates: [
        { field: "price", op: "lte", amount: "1000", currency: "EGP" },
      ],
      sort: "cheapest",
    });
  expect(
    filtered.body.candidates.every(
      (c: { product: ProductEvidence }) =>
        Number(c.product.price.amount) <= 1000,
    ),
  ).toBe(true);
  const stale = await request(app)
    .post("/__internal/catalogue/search")
    .set("x-service-secret", secret)
    .send({ ...query, query: "different", cursor: first.body.next_cursor });
  expect(stale.status).toBe(409);
});
it("retains unknown exclusions and handles literal search syntax without interpretation rules", async () => {
  const app = createApp({ serviceSecret: secret });
  const response = await request(app)
    .post("/__internal/catalogue/details")
    .set("x-service-secret", secret)
    .send({
      v: 1,
      ids: ["shoe-01", "does-not-exist"],
      requirements: [{ field: "feature", op: "exclude", value: "leather" }],
      unverified_requirements: [],
    });
  expect(response.status).toBe(200);
  expect(response.body.products[0].requirements).toEqual([
    { index: 0, status: "unknown" },
  ]);
  expect(response.body.missing_ids).toEqual(["does-not-exist"]);
  const injection = await request(app)
    .post("/__internal/catalogue/search")
    .set("x-service-secret", secret)
    .send({ ...query, query: '" OR *); DROP TABLE products; --' });
  expect(injection.status).toBe(200);
  expect(
    (
      await request(app)
        .post("/__internal/catalogue/search")
        .set("x-service-secret", secret)
        .send({ ...query, query: "Cairo Marathon" })
    ).body.candidates.some(
      (c: { product: ProductEvidence }) => c.product.id === "shoe-04",
    ),
  ).toBe(true);
});
it("bounds input/output and revalidates ETags against a canonical query", async () => {
  const app = createApp({ serviceSecret: secret });
  const first = await request(app)
    .post("/__internal/catalogue/search")
    .set("x-service-secret", secret)
    .send(query);
  expect(
    Buffer.byteLength(JSON.stringify(first.body), "utf8"),
  ).toBeLessThanOrEqual(32768);
  const unchanged = await request(app)
    .post("/__internal/catalogue/search")
    .set("x-service-secret", secret)
    .set("If-None-Match", first.headers.etag)
    .send(query);
  expect(unchanged.status).toBe(304);
  for (const payload of [
    { ...query, query: "ع".repeat(1025) },
    { ...query, sql: "SELECT *" },
    {
      ...query,
      predicates: [
        { field: "price", op: "lte", amount: "-1", currency: "EGP" },
      ],
    },
  ]) {
    expect(
      (
        await request(app)
          .post("/__internal/catalogue/search")
          .set("x-service-secret", secret)
          .send(payload)
      ).status,
    ).toBe(400);
  }
});

it("matches the shared wire fixtures", () => {
  const rows = JSON.parse(
    readFileSync(
      new URL("../../protocol/catalogue/fixtures.json", import.meta.url),
      "utf8",
    ),
  );
  for (const row of rows) {
    if (row.valid) expect(() => parseSearch(row.query)).not.toThrow();
    else expect(() => parseSearch(row.query)).toThrow();
  }
});
