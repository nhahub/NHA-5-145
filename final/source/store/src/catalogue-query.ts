import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import type { SQLInputValue } from "node:sqlite";
import { priceMinor } from "./catalogue-db.js";
import type {
  ProductRepository,
  ProductEvidence,
} from "./product-repository.js";

export type Predicate =
  | { field: "price"; op: "gte" | "lte"; amount: string; currency: "EGP" }
  | {
      field: "category" | "product_type" | "color" | "size" | "feature" | "use";
      op: "eq" | "exclude";
      value: string;
    }
  | { field: "available"; op: "eq"; value: boolean };
export interface SearchQuery {
  v: 1;
  query: string;
  predicates: Predicate[];
  requirements: Predicate[];
  unverified_requirements: string[];
  sort: "relevance" | "cheapest" | "newest";
  cursor: string | null;
}
export interface DetailsQuery {
  v: 1;
  ids: string[];
  requirements: Predicate[];
  unverified_requirements: string[];
}
export class CatalogueError extends Error {
  constructor(
    readonly code:
      | "invalid_query"
      | "stale_cursor"
      | "stale_index"
      | "record_too_large"
      | "unavailable",
  ) {
    super(code);
  }
}
function invalid(): never {
  throw new CatalogueError("invalid_query");
}
function object(value: unknown, keys: string[]): Record<string, unknown> {
  if (
    !value ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.keys(value).some((k) => !keys.includes(k)) ||
    keys.some((k) => !(k in value))
  )
    invalid();
  return value as Record<string, unknown>;
}
const norm = (value: string) => value.normalize("NFKC").trim().toLowerCase();
function string(value: unknown, max: number, empty = false): string {
  if (
    typeof value !== "string" ||
    [...value].length > max ||
    (!empty && !value.trim())
  )
    invalid();
  return value;
}
function predicates(value: unknown): Predicate[] {
  if (!Array.isArray(value) || value.length > 20) invalid();
  return value.map((item) => {
    if (item?.field === "price") {
      const p = object(item, ["field", "op", "amount", "currency"]);
      if (!["gte", "lte"].includes(String(p.op)) || p.currency !== "EGP")
        invalid();
      try {
        priceMinor(string(p.amount, 24));
      } catch {
        invalid();
      }
      return {
        field: "price",
        op: p.op,
        amount: p.amount,
        currency: "EGP",
      } as Predicate;
    }
    const p = object(item, ["field", "op", "value"]);
    if (p.field === "available") {
      if (p.op !== "eq" || typeof p.value !== "boolean") invalid();
    } else if (
      typeof p.field !== "string" ||
      typeof p.op !== "string" ||
      !["category", "product_type", "color", "size", "feature", "use"].includes(
        String(p.field),
      ) ||
      !["eq", "exclude"].includes(String(p.op))
    )
      invalid();
    else string(p.value, 200);
    return { field: p.field, op: p.op, value: p.value } as Predicate;
  });
}
function unverified(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > 20) invalid();
  return value.map((v) => string(v, 200));
}
export function parseSearch(input: unknown): SearchQuery {
  const body = object(input, [
    "v",
    "query",
    "predicates",
    "requirements",
    "unverified_requirements",
    "sort",
    "cursor",
  ]);
  if (
    body.v !== 1 ||
    typeof body.sort !== "string" ||
    !["relevance", "cheapest", "newest"].includes(String(body.sort))
  )
    invalid();
  const filters = predicates(body.predicates),
    requirements = predicates(body.requirements);
  if (
    new Set([...filters, ...requirements].map((p) => JSON.stringify(p))).size >
    20
  )
    invalid();
  return {
    v: 1,
    query: string(body.query, 1024, true),
    predicates: filters,
    requirements,
    unverified_requirements: unverified(body.unverified_requirements),
    sort: body.sort as SearchQuery["sort"],
    cursor: body.cursor === null ? null : string(body.cursor, 2048),
  };
}
export function parseDetails(input: unknown): DetailsQuery {
  const body = object(input, [
    "v",
    "ids",
    "requirements",
    "unverified_requirements",
  ]);
  if (
    body.v !== 1 ||
    !Array.isArray(body.ids) ||
    body.ids.length > 9 ||
    !body.ids.length
  )
    invalid();
  const ids = body.ids.map((id) => string(id, 100));
  if (new Set(ids).size !== ids.length) invalid();
  return {
    v: 1,
    ids,
    requirements: predicates(body.requirements),
    unverified_requirements: unverified(body.unverified_requirements),
  };
}
export function requirementStatus(
  product: ProductEvidence,
  p: Predicate,
): "satisfied" | "violated" | "unknown" {
  if (p.field === "price") {
    const actual = priceMinor(product.price.amount),
      expected = priceMinor(p.amount);
    return (p.op === "lte" ? actual <= expected : actual >= expected)
      ? "satisfied"
      : "violated";
  }
  if (p.field === "available")
    return product.available === p.value ? "satisfied" : "violated";
  const expected = norm(p.value);
  const values =
    p.field === "category"
      ? [product.category]
      : p.field === "product_type"
        ? [product.type]
        : p.field === "color"
          ? product.colors
          : p.field === "size"
            ? product.sizes
            : p.field === "feature"
              ? product.features
              : product.suitableFor;
  const present = values.some((v) => norm(v) === expected);
  if (p.field === "feature" || p.field === "use") {
    const absent = (
      p.field === "feature" ? product.absent_features : product.absent_uses
    ).some((v) => norm(v) === expected);
    if (!present && !absent) return "unknown";
  }
  return (p.op === "exclude" ? !present : present) ? "satisfied" : "violated";
}
export function candidate(
  repo: ProductRepository,
  id: string,
  requirements: Predicate[],
) {
  const product = repo.evidence(id)!;
  return {
    product,
    product_revision: repo.productRevision(id)!,
    requirements: requirements.map((p, index) => ({
      index,
      status: requirementStatus(product, p),
    })),
  };
}
export function digest(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}
function signature(body: string, key: string): string {
  return createHmac("sha256", key).update(body).digest("hex");
}
function cursorOffset(
  cursor: string | null,
  hash: string,
  revision: number,
  key: string,
): number {
  if (!cursor) return 0;
  try {
    const [body, sig, extra] = cursor.split(".");
    const expected = signature(body, key);
    if (
      extra ||
      !sig ||
      sig.length !== expected.length ||
      !timingSafeEqual(Buffer.from(sig), Buffer.from(expected))
    )
      throw new Error();
    const parsed = JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
    if (
      parsed.hash !== hash ||
      parsed.revision !== revision ||
      !Number.isSafeInteger(parsed.offset) ||
      parsed.offset < 0 ||
      parsed.offset > 1000000
    )
      throw new Error();
    return parsed.offset;
  } catch {
    throw new CatalogueError("stale_cursor");
  }
}
/** Conditions precede ranking/limits. Missing feature evidence remains inspectable, not verified. */
export function eligibleIds(
  repo: ProductRepository,
  filters: Predicate[],
): string[] {
  const clauses: string[] = [],
    args: SQLInputValue[] = [];
  for (const p of filters) {
    if (p.field === "price") {
      clauses.push(`price_minor ${p.op === "lte" ? "<=" : ">="} ?`);
      args.push(priceMinor(p.amount));
    } else if (p.field === "available") {
      clauses.push("available=?");
      args.push(Number(p.value));
    } else if (p.field === "category" || p.field === "product_type") {
      clauses.push(`lower(${p.field}) ${p.op === "eq" ? "=" : "!="} ?`);
      args.push(norm(p.value));
    } else {
      const open = p.field === "feature" || p.field === "use";
      clauses.push(
        `${open || p.op === "exclude" ? "NOT " : ""}EXISTS (SELECT 1 FROM product_attributes a WHERE a.product_id=products.id AND a.kind=? AND a.value=? AND a.present=?)`,
      );
      args.push(p.field, norm(p.value), open && p.op === "eq" ? 0 : 1);
    }
  }
  return repo.database
    .prepare(
      "SELECT id FROM products" +
        (clauses.length ? " WHERE " + clauses.join(" AND ") : "") +
        " ORDER BY ordinal",
    )
    .all(...args)
    .map((row) => String(row.id));
}
export function lexicalIds(repo: ProductRepository, query: string): string[] {
  const tokens = norm(query).match(/[\p{L}\p{N}]+/gu) ?? [];
  if (!tokens.length) return query.trim() ? [] : repo.all().map((p) => p.id);
  const match = tokens
    .map((token) => '"' + token.replaceAll('"', '""') + '"')
    .join(" OR ");
  return repo.database
    .prepare(
      "SELECT id FROM product_fts WHERE product_fts MATCH ? ORDER BY bm25(product_fts),id",
    )
    .all(match)
    .map((row) => String(row.id));
}
export type Ranker = (
  query: string,
  eligible: string[],
  lexical: string[],
) => string[];
export function searchProducts(
  repo: ProductRepository,
  query: SearchQuery,
  key: string,
  ranker?: Ranker,
) {
  const revision = repo.revision(),
    hash = digest({ ...query, cursor: null });
  const offset = cursorOffset(query.cursor, hash, revision, key);
  const eligible = eligibleIds(repo, query.predicates),
    ids = new Set(eligible);
  const lexical = lexicalIds(repo, query.query).filter((id) => ids.has(id));
  let ranked = ranker ? ranker(query.query, eligible, lexical) : lexical;
  if (query.sort !== "relevance")
    ranked = [...eligible].sort((a, b) => {
      const x = repo.get(a)!,
        y = repo.get(b)!;
      if (query.sort === "newest")
        return y.addedAt.localeCompare(x.addedAt) || a.localeCompare(b);
      const diff = priceMinor(x.price.amount) - priceMinor(y.price.amount);
      return diff === 0n ? a.localeCompare(b) : diff < 0 ? -1 : 1;
    });
  const selected = ranked
    .slice(offset, offset + 10)
    .map((id) => candidate(repo, id, query.requirements));
  const result = {
    v: 1 as const,
    catalogue_revision: revision,
    candidates: selected,
    ranking: ranker ? "hybrid" : "lexical",
    exact_count:
      query.query.trim() || query.unverified_requirements.length
        ? null
        : eligible.filter((id) =>
            [...query.predicates, ...query.requirements].every(
              (p) => requirementStatus(repo.evidence(id)!, p) === "satisfied",
            ),
          ).length,
    next_cursor: null as string | null,
    truncated: false,
    unverified_requirements: query.unverified_requirements,
  };
  const cursor = () => {
    const next = offset + result.candidates.length;
    if (next >= ranked.length) return null;
    const body = Buffer.from(
      JSON.stringify({ hash, revision, offset: next }),
    ).toString("base64url");
    return body + "." + signature(body, key);
  };
  result.next_cursor = cursor();
  while (
    Buffer.byteLength(JSON.stringify(result), "utf8") > 32768 &&
    result.candidates.length > 1
  ) {
    result.candidates.pop();
    result.truncated = true;
    result.next_cursor = cursor();
  }
  if (Buffer.byteLength(JSON.stringify(result), "utf8") > 32768)
    throw new CatalogueError("record_too_large");
  return result;
}
export function productDetails(repo: ProductRepository, query: DetailsQuery) {
  const result = {
    v: 1 as const,
    catalogue_revision: repo.revision(),
    products: query.ids
      .filter((id) => repo.get(id))
      .map((id) => candidate(repo, id, query.requirements)),
    missing_ids: query.ids.filter((id) => !repo.get(id)),
    unverified_requirements: query.unverified_requirements,
  };
  if (Buffer.byteLength(JSON.stringify(result), "utf8") > 32768)
    throw new CatalogueError("record_too_large");
  return result;
}
