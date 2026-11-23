import { randomUUID } from "node:crypto";

import type { Money } from "./catalogue.js";
import type { ProductRepository } from "./product-repository.js";

export type MutationKind = "clear_cart" | "submit_checkout";
export interface CartLine {
  product_id: string;
  quantity: number;
  size?: string;
  color?: string;
}

export function lineKey(
  line: Pick<CartLine, "product_id" | "size" | "color">,
): string {
  return [line.product_id, line.size ?? "", line.color ?? ""].join("~");
}

export interface OrderLine extends CartLine {
  name_ar: string;
  name_en: string;
  unit_price: Money;
}

interface UndoRecord {
  id: string;
  before: CartLine[];
  expiresAt: number;
  kind: string;
  line: string;
  revision: number;
}

interface Confirmation {
  kind: MutationKind;
  cartRevision: number;
  catalogueRevision: number;
  issuedAt: number;
}

/** Bounds that keep one stored Shopper record far below the store's size guard. */
export const MAX_RECENT_OPERATIONS = 200;
export const MAX_ORDERS = 20;

/**
 * Open Confirmations and the Undo record are single-process, short-lived state. They
 * are deliberately never persisted, so a restart ends them (a guarded action then
 * needs a new Confirmation). The registry keeps one holder per Shopper per process.
 */
export class CartEphemeral {
  confirmations = new Map<string, Confirmation>();
  undo: UndoRecord | null = null;
}

export interface CartSnapshot {
  lines: CartLine[];
  revision: number;
  terms: string;
  orders: Array<{ id: string; lines: OrderLine[] }>;
  operations: string[];
}

export class GuardedCart {
  #lines: CartLine[] = [];
  #revision = 0;
  #orders: Array<{ id: string; lines: OrderLine[] }> = [];
  #operations = new Set<string>();
  readonly #clock: () => number;
  readonly #eph: CartEphemeral;

  #terms = "";
  constructor(
    clock: () => number,
    readonly repository: ProductRepository,
    ephemeral: CartEphemeral = new CartEphemeral(),
  ) {
    this.#clock = clock;
    this.#eph = ephemeral;
  }

  /** The durable part of the cart: never Confirmations or the Undo record. */
  snapshot(): CartSnapshot {
    return JSON.parse(
      JSON.stringify({
        lines: this.#lines,
        revision: this.#revision,
        terms: this.#terms,
        orders: this.#orders,
        operations: [...this.#operations],
      }),
    ) as CartSnapshot;
  }

  /** Loads a stored cart; returns false when the stored shape is not valid. */
  restore(data: unknown): boolean {
    const d = data as Partial<CartSnapshot> | null;
    const okLine = (l: unknown): boolean => {
      const x = l as Partial<OrderLine> | null;
      return (
        typeof x === "object" &&
        x !== null &&
        typeof x.product_id === "string" &&
        Number.isSafeInteger(x.quantity)
      );
    };
    if (
      !d ||
      !Array.isArray(d.lines) ||
      !d.lines.every(okLine) ||
      !Number.isSafeInteger(d.revision) ||
      typeof d.terms !== "string" ||
      !Array.isArray(d.orders) ||
      !d.orders.every(
        (o) =>
          typeof o?.id === "string" &&
          Array.isArray(o.lines) &&
          o.lines.every(okLine),
      ) ||
      !Array.isArray(d.operations) ||
      !d.operations.every((o) => typeof o === "string")
    )
      return false;
    this.#lines = d.lines.map((line) => ({ ...line }));
    this.#revision = d.revision!;
    this.#terms = d.terms;
    this.#orders = d.orders.map((o) => ({ id: o.id, lines: [...o.lines] }));
    this.#operations = new Set(d.operations);
    return true;
  }

  get revision(): number {
    this.refreshProductTerms();
    return this.#revision;
  }

  get lines(): CartLine[] {
    return this.#lines.map((line) => ({ ...line }));
  }

  get state() {
    this.refreshProductTerms();
    return {
      revision: this.#revision,
      lines: this.lines,
      orders: this.#orders.map((order) => ({
        id: order.id,
        lines: order.lines.map((line) => ({
          ...line,
          unit_price: { ...line.unit_price },
        })),
      })),
    };
  }

  get undo() {
    const record = this.#eph.undo;
    const before = record?.before.find((line) => lineKey(line) === record.line);
    const after = this.#lines.find((line) => lineKey(line) === record?.line);
    const item = after ?? before;
    const product = item ? this.repository.get(item.product_id) : undefined;
    return record !== null &&
      record.expiresAt > this.#clock() &&
      record.revision === this.#revision
      ? {
          id: record.id,
          remaining_ms: record.expiresAt - this.#clock(),
          kind: record.kind,
          description: `${product?.nameAr ?? item?.product_id} · ${item?.size ?? "—"} / ${item?.color ?? "—"}: ${before?.quantity ?? 0} → ${after?.quantity ?? 0}`,
          description_en: `${product?.nameEn ?? item?.product_id} · ${item?.size ?? "—"} / ${item?.color ?? "—"}: ${before?.quantity ?? 0} → ${after?.quantity ?? 0}`,
        }
      : null;
  }

  edit(
    kind: "add" | "quantity" | "remove" | "undo",
    input: Record<string, unknown>,
  ): boolean {
    this.refreshProductTerms();
    const operation = input.operation_id;
    if (
      typeof operation !== "string" ||
      operation.length < 1 ||
      operation.length > 100 ||
      this.#operations.has(operation) ||
      input.revision !== this.#revision
    )
      return false;
    if (kind === "undo") {
      const undo = this.#eph.undo;
      if (undo === null || this.undo === null || input.undo_id !== undo.id)
        return false;
      this.#lines = undo.before.map((line) => ({ ...line }));
      this.#eph.undo = null;
    } else {
      const product =
        typeof input.product_id === "string"
          ? this.repository.get(input.product_id)
          : undefined;
      if (kind !== "remove" && (!product || !product.available)) return false;
      const size = typeof input.size === "string" ? input.size : undefined;
      const color = typeof input.color === "string" ? input.color : undefined;
      if (
        (kind === "add" || kind === "quantity") &&
        (!product!.sizes.includes(size ?? "") ||
          !product!.colors.includes(color ?? ""))
      )
        return false;
      const key = lineKey({
        product_id: String(input.product_id),
        size,
        color,
      });
      const index = this.#lines.findIndex((line) => lineKey(line) === key);
      if (kind !== "add" && index === -1) return false;
      const quantity = input.quantity;
      if (
        kind !== "remove" &&
        (typeof quantity !== "number" ||
          !Number.isSafeInteger(quantity) ||
          quantity < 1 ||
          quantity > 99)
      )
        return false;
      const nextQuantity =
        kind === "add"
          ? (this.#lines[index]?.quantity ?? 0) + Number(quantity)
          : Number(quantity);
      if (kind !== "remove" && nextQuantity > 99) return false;
      const previous = this.#eph.undo;
      const coalesce =
        kind === "quantity" &&
        this.undo !== null &&
        previous?.kind === kind &&
        previous.line === key;
      this.#eph.undo = coalesce
        ? { ...previous!, revision: this.#revision + 1 }
        : {
            id: randomUUID(),
            before: this.lines,
            expiresAt: this.#clock() + 10000,
            kind,
            line: key,
            revision: this.#revision + 1,
          };
      if (kind === "remove") this.#lines.splice(index, 1);
      else if (index !== -1) this.#lines[index].quantity = nextQuantity;
      else
        this.#lines.push({
          product_id: String(input.product_id),
          size,
          color,
          quantity: nextQuantity,
        });
    }
    this.#revision++;
    this.#operations.add(operation);
    if (this.#operations.size > MAX_RECENT_OPERATIONS)
      this.#operations.delete(this.#operations.values().next().value!);
    this.#eph.confirmations.clear();
    this.#terms = this.terms();
    return true;
  }

  seed(lines: CartLine[]): boolean {
    if (
      !Array.isArray(lines) ||
      lines.some(
        (line) =>
          typeof line.product_id !== "string" ||
          !Number.isSafeInteger(line.quantity) ||
          line.quantity < 1 ||
          line.quantity > 99 ||
          !this.repository.get(line.product_id)?.available,
      )
    )
      return false;
    this.#lines = lines.map((line) => ({ ...line }));
    this.#revision++;
    this.#eph.undo = null;
    this.#terms = this.terms();
    return true;
  }

  register(input: {
    token: string;
    task_id: string;
    kind: MutationKind;
    cart_revision: number;
  }): boolean {
    this.refreshProductTerms();
    if (
      !/^confirmation-[0-9a-f]{32}$/.test(input.token) ||
      !/^task-[a-zA-Z0-9-]+$/.test(input.task_id) ||
      !["clear_cart", "submit_checkout"].includes(input.kind) ||
      input.cart_revision !== this.#revision ||
      this.#lines.length === 0 ||
      this.#eph.confirmations.has(input.token)
    )
      return false;
    this.#eph.confirmations.set(input.token, {
      kind: input.kind,
      cartRevision: input.cart_revision,
      catalogueRevision: this.repository.revision(),
      issuedAt: this.#clock(),
    });
    return true;
  }

  consume(token: unknown, kind: MutationKind, revision: unknown): boolean {
    this.refreshProductTerms();
    if (typeof token !== "string") return false;
    const confirmation = this.#eph.confirmations.get(token);
    if (confirmation === undefined) return false;
    this.#eph.confirmations.delete(token);
    return (
      confirmation.kind === kind &&
      confirmation.catalogueRevision === this.repository.revision() &&
      (kind !== "submit_checkout" || this.purchasable()) &&
      confirmation.cartRevision === this.#revision &&
      String(confirmation.cartRevision) === revision &&
      this.#clock() - confirmation.issuedAt < 60_000 &&
      this.#lines.length > 0
    );
  }

  clear(): void {
    this.#lines = [];
    this.#revision++;
    this.#eph.undo = null;
    this.#terms = this.terms();
  }

  submitOrder(): string {
    this.refreshProductTerms();
    if (!this.purchasable())
      throw new Error("Cart products are no longer purchasable");
    const id = randomUUID();
    this.#orders.push({
      id,
      lines: this.lines.map((line) => {
        const product = this.repository.get(line.product_id)!;
        return {
          ...line,
          name_ar: product.nameAr,
          name_en: product.nameEn,
          unit_price: { ...product.price },
        };
      }),
    });
    if (this.#orders.length > MAX_ORDERS)
      this.#orders.splice(0, this.#orders.length - MAX_ORDERS);
    this.clear();
    return id;
  }

  private terms(): string {
    return JSON.stringify(
      this.#lines.map((line) => [
        line.product_id,
        this.repository.productRevision(line.product_id) ?? null,
      ]),
    );
  }
  refreshProductTerms(): void {
    const next = this.terms();
    if (this.#terms && this.#terms !== next) {
      this.#revision++;
      this.#eph.confirmations.clear();
      if (this.#eph.undo) this.#eph.undo.revision = this.#revision;
    }
    this.#terms = next;
  }
  private purchasable(): boolean {
    return (
      this.#lines.length > 0 &&
      this.#lines.every((line) => {
        const product = this.repository.get(line.product_id);
        return (
          product?.available &&
          (line.size === undefined || product.sizes.includes(line.size)) &&
          (line.color === undefined || product.colors.includes(line.color))
        );
      })
    );
  }

  reset(): void {
    this.#lines = [];
    this.#revision = 0;
    this.#eph.confirmations.clear();
    this.#orders = [];
    this.#eph.undo = null;
    this.#operations.clear();
    this.#terms = this.terms();
  }
}
