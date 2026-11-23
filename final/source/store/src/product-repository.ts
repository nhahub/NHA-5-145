import type { DatabaseSync } from "node:sqlite";
import {
  filterProductRecords,
  type Product,
  type ProductConstraints,
} from "./catalogue.js";

export interface ProductEvidence extends Product {
  absent_features: readonly string[];
  absent_uses: readonly string[];
}

/** Owns current catalogue facts; consumers never read the seed artifact. */
export class ProductRepository {
  constructor(readonly database: DatabaseSync) {}
  /** One synchronous request observes one catalogue version, including order prices. */
  snapshot<T>(read: () => T): T {
    this.database.exec("BEGIN");
    try {
      this.revision(); // Establish the SQLite read snapshot before any commerce checks.
      const result = read();
      this.database.exec("COMMIT");
      return result;
    } catch (error) {
      this.database.exec("ROLLBACK");
      throw error;
    }
  }
  revision(): number {
    return Number(
      this.database
        .prepare("SELECT revision FROM catalogue_meta WHERE id=1")
        .get()!.revision,
    );
  }
  all(): Product[] {
    return this.database
      .prepare("SELECT document FROM products ORDER BY ordinal")
      .all()
      .map((row) => JSON.parse(String(row.document)) as Product);
  }
  get(id: string): Product | undefined {
    const row = this.database
      .prepare("SELECT document FROM products WHERE id=?")
      .get(id);
    return row ? (JSON.parse(String(row.document)) as Product) : undefined;
  }
  evidence(id: string): ProductEvidence | undefined {
    const row = this.database
      .prepare(
        "SELECT document, absent_features, absent_uses FROM products WHERE id=?",
      )
      .get(id);
    return row
      ? ({
          ...JSON.parse(String(row.document)),
          absent_features: JSON.parse(String(row.absent_features)),
          absent_uses: JSON.parse(String(row.absent_uses)),
        } as ProductEvidence)
      : undefined;
  }
  productRevision(id: string): number | undefined {
    const row = this.database
      .prepare("SELECT revision FROM products WHERE id=?")
      .get(id);
    return row ? Number(row.revision) : undefined;
  }
  filter(constraints: ProductConstraints): Product[] {
    return filterProductRecords(this.all(), constraints);
  }
  close(): void {
    this.database.close();
  }
}
