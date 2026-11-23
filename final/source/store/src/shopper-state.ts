import type { ProductRepository } from "./product-repository.js";
import { createHash, randomBytes } from "node:crypto";
import { CartEphemeral, GuardedCart } from "./guarded-cart.js";
import type { ShopperStateStore } from "./shopper-state-store.js";

export const opaqueToken = (): string => randomBytes(32).toString("hex");
export const credentialDigest = (value: string): string =>
  createHash("sha256").update(value).digest("hex");
export interface ShopperBinding {
  shopper_id: string;
  generation: string;
}
export interface ShopperState {
  binding: ShopperBinding;
  cart: GuardedCart;
  csrf: string;
  loggedIn: boolean;
  lastActivity: number;
  /** Digest of the browser credential; the credential itself is never kept. */
  credentialDigest: string;
  /** What was last read or written in the store (for the conditional write). */
  stored?: {
    revision: number;
    /** The saved record without its activity time. */
    json: string;
    /** The activity time in the saved record. */
    activity: number;
  };
}

/** Commerce lifetime: seven days after the Shopper's last activity. */
export const SHOPPER_TTL_MS = 7 * 24 * 60 * 60 * 1000;
/**
 * A request that changes nothing saves nothing, unless the saved activity time is older
 * than this (so the seven days keep extending without a write on every request).
 */
const ACTIVITY_SAVE_INTERVAL_MS = 10 * 60 * 1000;

const RECORD_VERSION = 1;
const generationKey = "storefront:generation";
const shopperKey = (id: string): string => "storefront:shopper:" + id;
const credentialKey = (digest: string): string =>
  "storefront:credential:" + digest;

/**
 * Shopper commerce state, saved in a Shopper State Store so it survives a restart.
 * Each request loads the Shopper's record, and saves it again (conditional on the
 * revision it loaded) before the response is sent. Open Confirmations and the Undo
 * record live only in this process (see CartEphemeral).
 */
export class ShopperRegistry {
  readonly #active = new Map<string, number>();
  readonly #ephemeral = new Map<string, CartEphemeral>();
  readonly #clock: () => number;
  readonly #capacity: number;
  readonly #ttlMs: number;
  readonly #repository: ProductRepository;
  readonly #store: ShopperStateStore;
  #generation: Promise<string> | undefined;
  constructor(options: {
    repository: ProductRepository;
    store: ShopperStateStore;
    clock?: () => number;
    capacity?: number;
    ttlMs?: number;
  }) {
    this.#repository = options.repository;
    this.#store = options.store;
    this.#clock = options.clock ?? Date.now;
    this.#capacity = options.capacity ?? 100;
    this.#ttlMs = options.ttlMs ?? SHOPPER_TTL_MS;
  }

  /** The stored, stable generation the Agent's Shopper binding depends on. */
  generation(): Promise<string> {
    this.#generation ??= this.#loadGeneration().catch((error) => {
      this.#generation = undefined;
      throw error;
    });
    return this.#generation;
  }
  async #loadGeneration(): Promise<string> {
    const existing = await this.#store.read(generationKey);
    const known = (existing?.value as { generation?: unknown } | undefined)
      ?.generation;
    if (typeof known === "string" && known) return known;
    const generation = opaqueToken();
    const written = await this.#store.write(
      generationKey,
      { generation },
      {
        expiresAt: null,
        expectedRevision: existing ? existing.revision : null,
      },
    );
    if (written.ok) return generation;
    const winner = (await this.#store.read(generationKey))?.value as
      | { generation?: unknown }
      | undefined;
    if (typeof winner?.generation !== "string")
      throw new Error("Storefront generation could not be saved");
    return winner.generation;
  }

  /** Capacity counts Shoppers active in this process; inactive ones age out. */
  #expire(): void {
    for (const [id, last] of this.#active)
      if (this.#clock() - last >= this.#ttlMs) {
        this.#active.delete(id);
        this.#ephemeral.delete(id);
      }
  }
  #cart(id: string): GuardedCart {
    let holder = this.#ephemeral.get(id);
    if (!holder) {
      holder = new CartEphemeral();
      this.#ephemeral.set(id, holder);
    }
    return new GuardedCart(this.#clock, this.#repository, holder);
  }

  /** A new Shopper; nothing is stored until the first save. */
  async create(): Promise<
    { credential: string; state: ShopperState } | undefined
  > {
    this.#expire();
    if (this.#active.size >= this.#capacity) return undefined;
    const credential = opaqueToken();
    const id = opaqueToken();
    const state: ShopperState = {
      binding: { shopper_id: id, generation: await this.generation() },
      cart: this.#cart(id),
      csrf: opaqueToken(),
      loggedIn: false,
      lastActivity: this.#clock(),
      credentialDigest: credentialDigest(credential),
    };
    this.#active.set(id, state.lastActivity);
    return { credential, state };
  }

  async resolve(
    credential: string,
    touch = true,
  ): Promise<ShopperState | undefined> {
    this.#expire();
    const digest = credentialDigest(credential);
    const link = await this.#store.read(credentialKey(digest));
    const id = (link?.value as { shopper_id?: unknown } | undefined)
      ?.shopper_id;
    if (typeof id !== "string") return undefined;
    const state = await this.#load(id);
    if (!state || state.credentialDigest !== digest) return undefined;
    if (touch) this.touch(state);
    return state;
  }

  async lookup(binding: ShopperBinding): Promise<ShopperState | undefined> {
    this.#expire();
    const bound = binding as Partial<ShopperBinding> | null;
    if (
      typeof bound?.shopper_id !== "string" ||
      bound.generation !== (await this.generation())
    )
      return undefined;
    return this.#load(bound.shopper_id);
  }

  /** Authenticated browser activity extends commerce expiry. */
  touch(state: ShopperState): void {
    state.lastActivity = this.#clock();
    this.#active.set(state.binding.shopper_id, state.lastActivity);
  }

  async #load(id: string): Promise<ShopperState | undefined> {
    const record = await this.#store.read(shopperKey(id));
    if (!record) return undefined;
    const state = this.#parse(id, record.value);
    if (!state || this.#clock() - state.lastActivity >= this.#ttlMs) {
      await this.#store.delete(shopperKey(id));
      if (state)
        await this.#store.delete(credentialKey(state.credentialDigest));
      return undefined;
    }
    state.stored = {
      revision: record.revision,
      json: this.#content(state),
      activity: state.lastActivity,
    };
    if (!this.#active.has(id)) this.#active.set(id, state.lastActivity);
    return state;
  }

  #parse(id: string, value: unknown): ShopperState | undefined {
    const d = value as Record<string, unknown> | null;
    const binding = d?.binding as Partial<ShopperBinding> | undefined;
    if (
      !d ||
      d.v !== RECORD_VERSION ||
      binding?.shopper_id !== id ||
      typeof binding.generation !== "string" ||
      typeof d.csrf !== "string" ||
      typeof d.logged_in !== "boolean" ||
      !Number.isFinite(d.last_activity) ||
      typeof d.credential_digest !== "string"
    )
      return undefined;
    const cart = this.#cart(id);
    if (!cart.restore(d.cart)) return undefined;
    return {
      binding: { shopper_id: id, generation: binding.generation },
      cart,
      csrf: d.csrf,
      loggedIn: d.logged_in,
      lastActivity: d.last_activity as number,
      credentialDigest: d.credential_digest,
    };
  }

  #document(state: ShopperState): Record<string, unknown> {
    return {
      v: RECORD_VERSION,
      binding: state.binding,
      csrf: state.csrf,
      logged_in: state.loggedIn,
      last_activity: state.lastActivity,
      credential_digest: state.credentialDigest,
      cart: state.cart.snapshot(),
    };
  }

  #content(state: ShopperState): string {
    const document = this.#document(state);
    delete document.last_activity;
    return JSON.stringify(document);
  }

  /**
   * Saves the Shopper (write-through). Returns "conflict" when someone else saved the
   * record since it was loaded; throws when the store fails or the record is too big.
   * The document is built synchronously, before the first await.
   */
  async save(state: ShopperState): Promise<"saved" | "conflict"> {
    const document = this.#document(state);
    const json = this.#content(state);
    if (
      state.stored?.json === json &&
      state.lastActivity - state.stored.activity < ACTIVITY_SAVE_INTERVAL_MS
    )
      return "saved";
    const expiresAt = state.lastActivity + this.#ttlMs;
    const written = await this.#store.write(
      shopperKey(state.binding.shopper_id),
      document,
      { expiresAt, expectedRevision: state.stored?.revision ?? null },
    );
    if (!written.ok) return "conflict";
    state.stored = {
      revision: written.revision,
      json,
      activity: state.lastActivity,
    };
    await this.#store.write(
      credentialKey(state.credentialDigest),
      { shopper_id: state.binding.shopper_id },
      { expiresAt },
    );
    return "saved";
  }
}
