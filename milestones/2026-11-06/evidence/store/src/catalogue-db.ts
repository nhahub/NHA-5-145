import { DatabaseSync } from "node:sqlite";
import { existsSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { categories, money, type Product } from "./catalogue.js";
import {
  ProductRepository,
  type ProductEvidence,
} from "./product-repository.js";

function strings(value: unknown): string[] {
  if (
    !Array.isArray(value) ||
    value.length > 100 ||
    value.some(
      (v) => typeof v !== "string" || !v.trim() || [...v].length > 200,
    ) ||
    new Set(value).size !== value.length
  )
    throw new Error("Invalid catalogue string list");
  return [...value];
}
function text(value: unknown, max = 200): string {
  if (typeof value !== "string" || !value.trim() || [...value].length > max)
    throw new Error("Invalid catalogue text");
  return value;
}
export function priceMinor(amount: string): bigint {
  money(amount);
  const [whole, fraction = ""] = amount.split(".");
  const value = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
  if (value > 9223372036854775807n)
    throw new Error("Catalogue price exceeds storage bound");
  return value;
}
function validate(input: Product): ProductEvidence {
  const raw = input as Product & Partial<ProductEvidence>;
  const amount = text(raw.price?.amount);
  priceMinor(amount);
  if (
    raw.price.currency !== "EGP" ||
    !categories.includes(raw.category) ||
    typeof raw.available !== "boolean" ||
    !/^\d{4}-\d{2}-\d{2}$/.test(raw.addedAt) ||
    ![null, "upper", "lower"].includes(raw.wearPosition)
  )
    throw new Error("Invalid catalogue product");
  const record: ProductEvidence = {
    id: text(raw.id, 100),
    category: raw.category,
    nameAr: text(raw.nameAr),
    nameEn: text(raw.nameEn),
    type: text(raw.type),
    price: money(amount),
    sizes: strings(raw.sizes),
    colors: strings(raw.colors),
    available: raw.available,
    addedAt: raw.addedAt,
    features: strings(raw.features),
    suitableFor: strings(raw.suitableFor),
    wearPosition: raw.wearPosition,
    absent_features: strings(raw.absent_features ?? []),
    absent_uses: strings(raw.absent_uses ?? []),
  };
  if (
    !/^[a-z0-9][a-z0-9-]*$/.test(record.id) ||
    record.features.some((v) =>
      record.absent_features.some(
        (a) =>
          a.normalize("NFKC").trim().toLowerCase() ===
          v.normalize("NFKC").trim().toLowerCase(),
      ),
    ) ||
    record.suitableFor.some((v) =>
      record.absent_uses.some(
        (a) =>
          a.normalize("NFKC").trim().toLowerCase() ===
          v.normalize("NFKC").trim().toLowerCase(),
      ),
    )
  )
    throw new Error("Contradictory or invalid catalogue fact");
  return record;
}
const schema = `
CREATE TABLE IF NOT EXISTS catalogue_meta(id INTEGER PRIMARY KEY CHECK(id=1), schema_version INTEGER NOT NULL, revision INTEGER NOT NULL);
INSERT OR IGNORE INTO catalogue_meta VALUES(1,1,0);
CREATE TABLE IF NOT EXISTS products(
 id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL, revision INTEGER NOT NULL,
 document TEXT NOT NULL, absent_features TEXT NOT NULL, absent_uses TEXT NOT NULL,
 category TEXT NOT NULL, product_type TEXT NOT NULL, price_minor INTEGER NOT NULL,
 available INTEGER NOT NULL, added_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS product_attributes(
 product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, value TEXT NOT NULL, present INTEGER NOT NULL,
 PRIMARY KEY(product_id,kind,value));
CREATE INDEX IF NOT EXISTS attributes_lookup ON product_attributes(kind,value,present,product_id);
CREATE INDEX IF NOT EXISTS products_filter ON products(category,available,price_minor);
CREATE VIRTUAL TABLE IF NOT EXISTS product_fts USING fts5(id UNINDEXED,text,tokenize='unicode61');
`;
function connect(path: string): DatabaseSync {
  const db = new DatabaseSync(path);
  db.exec("PRAGMA foreign_keys=ON; PRAGMA busy_timeout=3000;");
  return db;
}
export function openCatalogue(path: string): ProductRepository {
  if (!existsSync(path))
    throw new Error(
      "Catalogue database missing; run the explicit catalogue import command",
    );
  const db = connect(path);
  try {
    const meta = db
      .prepare("SELECT schema_version, revision FROM catalogue_meta WHERE id=1")
      .get();
    if (meta?.schema_version !== 1 || Number(meta.revision) < 1)
      throw new Error("Unsupported or uninitialized catalogue database");
    return new ProductRepository(db);
  } catch (error) {
    db.close();
    throw error;
  }
}
export function importCatalogue(
  path: string,
  products: readonly Product[],
): void {
  const records = products.map(validate);
  if (
    !records.length ||
    new Set(records.map((p) => p.id)).size !== records.length
  )
    throw new Error("Catalogue IDs must be nonempty and unique");
  mkdirSync(dirname(path), { recursive: true });
  const db = connect(path);
  try {
    db.exec("BEGIN IMMEDIATE");
    db.exec(schema);
    const meta = db
      .prepare("SELECT schema_version,revision FROM catalogue_meta WHERE id=1")
      .get()!;
    if (meta.schema_version !== 1)
      throw new Error("Unsupported catalogue schema");
    const before = db
      .prepare(
        "SELECT id,revision,document,absent_features,absent_uses FROM products ORDER BY ordinal",
      )
      .all();
    const next = records.map(
      ({ absent_features, absent_uses, ...product }) => ({
        document: JSON.stringify(product),
        absent_features: JSON.stringify(absent_features),
        absent_uses: JSON.stringify(absent_uses),
      }),
    );
    const unchanged =
      before.length === next.length &&
      before.every(
        (row, i) =>
          row.document === next[i].document &&
          row.absent_features === next[i].absent_features &&
          row.absent_uses === next[i].absent_uses,
      );
    if (!unchanged) {
      const revision = Number(meta.revision) + 1;
      db.exec(
        "DELETE FROM product_attributes; DELETE FROM products; DELETE FROM product_fts;",
      );
      const insert = db.prepare(
        "INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?)",
      );
      const attribute = db.prepare(
        "INSERT INTO product_attributes VALUES(?,?,?,?)",
      );
      const fts = db.prepare("INSERT INTO product_fts VALUES(?,?)");
      records.forEach((record, i) => {
        const old = before.find((r) => r.id === record.id);
        const same =
          old &&
          old.document === next[i].document &&
          old.absent_features === next[i].absent_features &&
          old.absent_uses === next[i].absent_uses;
        insert.run(
          record.id,
          i,
          same ? Number(old.revision) : revision,
          next[i].document,
          next[i].absent_features,
          next[i].absent_uses,
          record.category,
          record.type,
          priceMinor(record.price.amount),
          Number(record.available),
          record.addedAt,
        );
        for (const [kind, values, present] of [
          ["color", record.colors, 1],
          ["size", record.sizes, 1],
          ["feature", record.features, 1],
          ["use", record.suitableFor, 1],
          ["feature", record.absent_features, 0],
          ["use", record.absent_uses, 0],
        ] as const)
          for (const value of values)
            attribute.run(
              record.id,
              kind,
              value.normalize("NFKC").trim().toLowerCase(),
              present,
            );
        fts.run(
          record.id,
          [
            record.nameAr,
            record.nameEn,
            record.type,
            ...record.colors,
            ...record.features,
            ...record.suitableFor,
          ].join(" "),
        );
      });
      db.prepare("UPDATE catalogue_meta SET revision=? WHERE id=1").run(
        revision,
      );
    }
    db.exec("COMMIT");
  } catch (error) {
    if (db.isTransaction) db.exec("ROLLBACK");
    throw error;
  } finally {
    db.close();
  }
}
export function exportCatalogue(path: string): readonly ProductEvidence[] {
  const repo = openCatalogue(path);
  try {
    return repo.all().map((p) => repo.evidence(p.id)!);
  } finally {
    repo.close();
  }
}
