import { afterEach, expect, it } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { importCatalogue, openCatalogue } from "../src/catalogue-db.js";
import { seedProducts } from "../src/catalogue-seed.js";
import { parseSearch, searchProducts } from "../src/catalogue-query.js";
const base = {
  v: 1,
  query: "",
  predicates: [],
  requirements: [],
  unverified_requirements: [],
  sort: "relevance",
  cursor: null,
};
const cleanup: (() => void)[] = [];
afterEach(() => {
  for (const fn of cleanup.splice(0).reverse()) fn();
});
function fixture() {
  const dir = mkdtempSync(join(tmpdir(), "catalogue-category-"));
  cleanup.push(() => rmSync(dir, { recursive: true, force: true }));
  const file = join(dir, "catalogue.sqlite");
  importCatalogue(file, seedProducts);
  const repo = openCatalogue(file);
  cleanup.push(() => repo.close());
  return { file, repo };
}
it("retrieves canonical categories from product data with hard filters preserved", () => {
  const { repo } = fixture();
  for (const category of new Set(seedProducts.map((p) => p.category))) {
    const result = searchProducts(
      repo,
      parseSearch({
        ...base,
        query: category,
        predicates: [{ field: "available", op: "eq", value: true }],
      }),
      "synthetic-secret",
    );
    expect(result.candidates.length).toBeGreaterThan(0);
    for (const row of result.candidates) {
      expect(row.product.category).toBe(category);
      expect(row.product.available).toBe(true);
    }
  }
});
it("repairs an older index on explicit unchanged-data import and remains idempotent", () => {
  const { file, repo } = fixture();
  repo.database.exec("UPDATE product_fts SET text='legacy name only'");
  const revision = repo.revision();
  importCatalogue(file, seedProducts);
  expect(
    searchProducts(
      repo,
      parseSearch({ ...base, query: "shoes" }),
      "synthetic-secret",
    ).candidates.length,
  ).toBeGreaterThan(0);
  expect(repo.revision()).toBe(revision + 1);
  importCatalogue(file, seedProducts);
  expect(repo.revision()).toBe(revision + 1);
});

it("migrates a populated unicode61 index and stems terms before applying structured filters", () => {
  const { file, repo } = fixture();
  // Keep the same indexed text so only the old tokenizer triggers migration.
  repo.database.exec(`
    CREATE TEMP TABLE previous_fts AS SELECT id,text FROM product_fts;
    DROP TABLE product_fts;
    CREATE VIRTUAL TABLE product_fts USING fts5(id UNINDEXED,text,tokenize='unicode61');
    INSERT INTO product_fts SELECT id,text FROM previous_fts;
    DROP TABLE previous_fts;
  `);
  function ids(query: string) {
    return searchProducts(
      repo,
      parseSearch({
        ...base,
        query,
        predicates: [
          { field: "category", op: "eq", value: "shoes" },
          { field: "price", op: "lte", amount: "1500", currency: "EGP" },
        ],
      }),
      "synthetic-secret",
    ).candidates.map((candidate) => candidate.product.id);
  }
  expect(ids("walking")).toEqual([]);
  const revision = repo.revision();
  importCatalogue(file, seedProducts);
  expect(
    repo.database
      .prepare("SELECT sql FROM sqlite_schema WHERE name='product_fts'")
      .get()?.sql,
  ).toContain("porter unicode61");
  expect(ids("shoes")).toContain("shoe-06");
  expect(ids("shoe")).toEqual(ids("shoes"));
  expect(ids("walking")).toEqual(["shoe-06"]);
  expect(ids("walk")).toEqual(ids("walking"));
  expect(repo.all()).toHaveLength(seedProducts.length);
  importCatalogue(file, seedProducts);
  expect(repo.revision()).toBe(revision + 1);
});
