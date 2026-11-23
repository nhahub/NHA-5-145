import { JSDOM } from "jsdom";
import { describe, expect, it, vi } from "vitest";

import { executeAction } from "../src/actions.js";
import { BridgeRuntime, type StorageLike } from "../src/runtime.js";
import { SnapshotBuilder } from "../src/snapshot.js";
import { parseAction, type Action } from "../src/types.js";

class MemoryStorage implements StorageLike {
  values = new Map<string, string>();
  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }
  removeItem(key: string): void {
    this.values.delete(key);
  }
  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

function cart() {
  const dom = new JSDOM(
    '<form action="/cart/clear" method="post"><input type="hidden" name="cart_revision" value="3"><input type="hidden" name="copilot_confirmation" value=""><button data-guarded-mutation="clear_cart" data-cart-revision="3">Empty cart</button></form>',
    { url: "http://localhost:4000/cart" },
  );
  const button = dom.window.document.querySelector("button")!;
  const clicked = vi.fn((event: Event) => event.preventDefault());
  button.addEventListener("click", clicked);
  const builder = new SnapshotBuilder(dom.window.document, {
    isVisible: () => true,
  });
  return { builder, clicked, document: dom.window.document };
}

function base(type: Action["type"], id: number): Action {
  return {
    v: 1,
    type: type as "click",
    task_id: "task-1",
    action_id: "action-1",
    sequence_number: 1,
    narration: "Clear the cart",
    id,
  };
}

describe("Guarded Mutation boundary", () => {
  it("publishes only non-sensitive stable form and cart revision metadata", () => {
    const { builder } = cart();
    const button = builder
      .build()
      .elements.find((item) => item.role === "button");

    expect(button).toMatchObject({
      name: "Empty cart",
      form_action: "/cart/clear",
      mutation_state: "cart:3",
    });
  });

  it("rejects malformed guarded authority at the Action wire boundary", () => {
    const action = {
      ...base("click", 7),
      type: "guarded_click",
      confirmation_id: "confirmation-1234567890abcdef1234567890abcdef",
      mutation_kind: "clear_cart",
      target_signature: "button|Empty cart|POST /cart/clear",
      state_signature: "cart:3",
      cart_revision: 3,
      effect: "Remove every item from the current cart",
    };
    expect(() => parseAction({ ...action, confirmation_id: "yes" })).toThrow();
    expect(() => parseAction({ ...action, target_signature: "" })).toThrow();
    expect(() => parseAction({ ...action, cart_revision: -1 })).toThrow();
  });

  it("blocks an ordinary click on a guarded form even when it is same-origin", async () => {
    const { builder, clicked } = cart();
    const id = builder
      .build()
      .elements.find((item) => item.role === "button")!.id;

    const result = await executeAction(base("click", id), {
      builder,
      currentUrl: () => "http://localhost:4000/cart",
      storefrontOrigin: "http://localhost:4000",
      navigate: async () => undefined,
      settle: async () => undefined,
    });

    expect(result.status).toBe("blocked");
    expect(clicked).not.toHaveBeenCalled();
  });

  it("executes only a matching confirmed action and sends its opaque token through the native form", async () => {
    const { builder, clicked, document } = cart();
    const id = builder
      .build()
      .elements.find((item) => item.role === "button")!.id;
    const confirmationId = "confirmation-1234567890abcdef1234567890abcdef";
    const action = {
      ...base("click", id),
      type: "guarded_click",
      confirmation_id: confirmationId,
      mutation_kind: "clear_cart",
      target_signature: "button|Empty cart|POST /cart/clear",
      state_signature: "cart:3",
      cart_revision: 3,
      effect: "Remove every item from the current cart",
    } as Action;
    const result = await executeAction(action, {
      builder,
      currentUrl: () => "http://localhost:4000/cart",
      storefrontOrigin: "http://localhost:4000",
      navigate: async () => undefined,
      settle: async () => undefined,
    });

    expect(result.status).toBe("ok");
    expect(clicked).toHaveBeenCalledTimes(1);
    expect(
      document.querySelector<HTMLInputElement>(
        'input[name="copilot_confirmation"]',
      )?.value,
    ).toBe(confirmationId);
  });

  it("refuses a confirmed action when the cart revision changes before execution", async () => {
    const { builder, clicked } = cart();
    const id = builder
      .build()
      .elements.find((item) => item.role === "button")!.id;
    const action = {
      ...base("click", id),
      type: "guarded_click",
      confirmation_id: "confirmation-1234567890abcdef1234567890abcdef",
      mutation_kind: "clear_cart",
      target_signature: "button|Empty cart|POST /cart/clear",
      state_signature: "cart:2",
      cart_revision: 2,
      effect: "Remove every item from the current cart",
    } as Action;

    const result = await executeAction(action, {
      builder,
      currentUrl: () => "http://localhost:4000/cart",
      storefrontOrigin: "http://localhost:4000",
      navigate: async () => undefined,
      settle: async () => undefined,
    });

    expect(result.status).toBe("blocked");
    expect(clicked).not.toHaveBeenCalled();
  });

  it("carries a guarded form result across the Storefront reload only once", async () => {
    const { document } = cart();
    const storage = new MemoryStorage();
    const firstPosted: unknown[] = [];
    const first = new BridgeRuntime({
      document,
      panelOrigin: "http://localhost:4100",
      storage,
      currentUrl: () => "http://localhost:4000/cart",
      navigate: () => undefined,
      post: (message) => firstPosted.push(message),
      settle: async () => undefined,
      isVisible: () => true,
    });
    const button = first
      .snapshot()
      .elements.find((item) => item.role === "button")!;
    const action = {
      ...base("click", button.id),
      type: "guarded_click",
      confirmation_id: "confirmation-1234567890abcdef1234567890abcdef",
      mutation_kind: "clear_cart",
      target_signature: "button|Empty cart|POST /cart/clear",
      state_signature: "cart:3",
      cart_revision: 3,
      effect: "Remove every item from the current cart",
    } as Action;

    await first.receive("http://localhost:4100", { type: "action", action });
    expect(firstPosted).toEqual([]);

    const reloaded = new JSDOM("<h2>السلة فارغة</h2>", {
      url: "http://localhost:4000/cart",
    });
    const secondPosted: unknown[] = [];
    const second = new BridgeRuntime({
      document: reloaded.window.document,
      panelOrigin: "http://localhost:4100",
      storage,
      currentUrl: () => "http://localhost:4000/cart",
      navigate: () => undefined,
      post: (message) => secondPosted.push(message),
      isVisible: () => true,
    });
    second.start();
    expect(secondPosted).toEqual([
      {
        type: "action_result",
        result: expect.objectContaining({
          action_id: action.action_id,
          status: "navigated",
        }),
      },
    ]);
  });
});
