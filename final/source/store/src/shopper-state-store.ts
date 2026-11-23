import { DatabaseSync } from "node:sqlite";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";

/** One stored record may never approach DynamoDB's 400 KB item limit. */
export const MAX_RECORD_BYTES = 256 * 1024;

export class RecordTooLargeError extends Error {
  constructor(readonly bytes: number) {
    super(`Shopper state record is too large (${bytes} bytes)`);
  }
}

export interface StoredRecord {
  value: unknown;
  /** Counts successful writes of this key, starting at 1. */
  revision: number;
  /** Epoch milliseconds; null means the record never expires. */
  expiresAt: number | null;
}

export type WriteResult = { ok: true; revision: number } | { ok: false };

export interface WriteOptions {
  expiresAt: number | null;
  /**
   * undefined: write unconditionally. null: the key must not exist. A number: the
   * stored revision must equal it. A refused write returns { ok: false }.
   */
  expectedRevision?: number | null;
}

/**
 * Where the Storefront keeps Shopper state. Every implementation must satisfy the
 * storage contract suite (tests/shopper-state-store.contract.ts); the DynamoDB
 * adapter plugs into the same suite.
 */
export interface ShopperStateStore {
  /** Returns the record, or undefined when it is missing or has expired. */
  read(key: string): Promise<StoredRecord | undefined>;
  /** Throws RecordTooLargeError (and writes nothing) when the value is too big. */
  write(
    key: string,
    value: unknown,
    options: WriteOptions,
  ): Promise<WriteResult>;
  delete(key: string): Promise<void>;
  close?(): void;
}

export interface StoreOptions {
  clock?: () => number;
  maxRecordBytes?: number;
}

function encode(value: unknown, maximum: number): string {
  const json = JSON.stringify(value);
  const bytes = Buffer.byteLength(json, "utf8");
  if (bytes > maximum) throw new RecordTooLargeError(bytes);
  return json;
}

/** Decides whether a conditional write may proceed against the live record. */
function allowed(
  current: { revision: number } | undefined,
  expected: number | null | undefined,
): boolean {
  if (expected === undefined) return true;
  return expected === null
    ? current === undefined
    : current?.revision === expected;
}

export class MemoryShopperStateStore implements ShopperStateStore {
  readonly #records = new Map<
    string,
    { json: string; revision: number; expiresAt: number | null }
  >();
  readonly #clock: () => number;
  readonly #maximum: number;
  constructor(options: StoreOptions = {}) {
    this.#clock = options.clock ?? Date.now;
    this.#maximum = options.maxRecordBytes ?? MAX_RECORD_BYTES;
  }
  #live(key: string) {
    const row = this.#records.get(key);
    if (row && row.expiresAt !== null && row.expiresAt <= this.#clock()) {
      this.#records.delete(key);
      return undefined;
    }
    return row;
  }
  async read(key: string): Promise<StoredRecord | undefined> {
    const row = this.#live(key);
    return row
      ? {
          value: JSON.parse(row.json),
          revision: row.revision,
          expiresAt: row.expiresAt,
        }
      : undefined;
  }
  async write(
    key: string,
    value: unknown,
    options: WriteOptions,
  ): Promise<WriteResult> {
    const json = encode(value, this.#maximum);
    const current = this.#live(key);
    if (!allowed(current, options.expectedRevision)) return { ok: false };
    const revision = (current?.revision ?? 0) + 1;
    this.#records.set(key, { json, revision, expiresAt: options.expiresAt });
    return { ok: true, revision };
  }
  async delete(key: string): Promise<void> {
    this.#records.delete(key);
  }
}

/** Local file store (Node's built-in SQLite). Survives Storefront restarts. */
export class SqliteShopperStateStore implements ShopperStateStore {
  readonly #database: DatabaseSync;
  readonly #clock: () => number;
  readonly #maximum: number;
  constructor(path: string, options: StoreOptions = {}) {
    this.#clock = options.clock ?? Date.now;
    this.#maximum = options.maxRecordBytes ?? MAX_RECORD_BYTES;
    mkdirSync(dirname(path), { recursive: true });
    this.#database = new DatabaseSync(path);
    this.#database.exec(
      `PRAGMA busy_timeout=5000;
       CREATE TABLE IF NOT EXISTS shopper_state (
         key TEXT PRIMARY KEY,
         value TEXT NOT NULL,
         revision INTEGER NOT NULL,
         expires_at INTEGER
       )`,
    );
  }
  #row(key: string) {
    const row = this.#database
      .prepare(
        "SELECT value, revision, expires_at FROM shopper_state WHERE key=?",
      )
      .get(key);
    if (!row) return undefined;
    const expiresAt = row.expires_at === null ? null : Number(row.expires_at);
    if (expiresAt !== null && expiresAt <= this.#clock()) {
      this.#database.prepare("DELETE FROM shopper_state WHERE key=?").run(key);
      return undefined;
    }
    return {
      json: String(row.value),
      revision: Number(row.revision),
      expiresAt,
    };
  }
  async read(key: string): Promise<StoredRecord | undefined> {
    const row = this.#row(key);
    return row
      ? {
          value: JSON.parse(row.json),
          revision: row.revision,
          expiresAt: row.expiresAt,
        }
      : undefined;
  }
  async write(
    key: string,
    value: unknown,
    options: WriteOptions,
  ): Promise<WriteResult> {
    const json = encode(value, this.#maximum);
    // IMMEDIATE takes the write lock first, so the revision check and the write are
    // one step even when another process (or app instance) uses the same file.
    this.#database.exec("BEGIN IMMEDIATE");
    try {
      const current = this.#row(key);
      if (!allowed(current, options.expectedRevision)) {
        this.#database.exec("ROLLBACK");
        return { ok: false };
      }
      const revision = (current?.revision ?? 0) + 1;
      this.#database
        .prepare(
          `INSERT INTO shopper_state (key, value, revision, expires_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value,
             revision=excluded.revision, expires_at=excluded.expires_at`,
        )
        .run(key, json, revision, options.expiresAt);
      this.#database.exec("COMMIT");
      return { ok: true, revision };
    } catch (error) {
      this.#database.exec("ROLLBACK");
      throw error;
    }
  }
  async delete(key: string): Promise<void> {
    this.#database.prepare("DELETE FROM shopper_state WHERE key=?").run(key);
  }
  close(): void {
    this.#database.close();
  }
}
