import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

import { BridgeRuntime, type StorageLike } from "../src/runtime.js";
import type { ClickAction, NavigateAction } from "../src/types.js";

class MemoryStorage implements StorageLike {
  readonly values = new Map<string, string>();

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

function action(): NavigateAction {
  return {
    v: 1,
    type: "navigate",
    task_id: "task-1",
    action_id: "action-1",
    sequence_number: 1,
    narration: "Applying filters.",
    url: "/c/shoes?type=running&max_price=2000",
  };
}

describe("BridgeRuntime", () => {
  it("returns a fresh Snapshot when the Panel requests one", async () => {
    const dom = new JSDOM(
      "<!doctype html><html><head><title>Store</title></head><body><h1>Home</h1></body></html>",
      { url: "http://localhost:4000/" },
    );
    const posted: unknown[] = [];
    const runtime = new BridgeRuntime({
      document: dom.window.document,
      panelOrigin: "http://localhost:4100",
      storage: new MemoryStorage(),
      currentUrl: () => dom.window.location.href,
      navigate: () => undefined,
      post: (message) => posted.push(message),
      settle: async () => undefined,
      isVisible: () => true,
    });

    await runtime.receive("http://localhost:4100", {
      type: "request_snapshot",
    });

    expect(posted).toEqual([
      {
        type: "snapshot",
        snapshot: expect.objectContaining({
          url: "http://localhost:4000/",
          title: "Store",
        }),
      },
    ]);
  });

  it("ignores messages outside the configured Panel origin", async () => {
    const dom = new JSDOM(
      "<!doctype html><html><body><h1>Home</h1></body></html>",
      {
        url: "http://localhost:4000/",
      },
    );
    const posted: unknown[] = [];
    const runtime = new BridgeRuntime({
      document: dom.window.document,
      panelOrigin: "http://localhost:4100",
      storage: new MemoryStorage(),
      currentUrl: () => dom.window.location.href,
      navigate: () => undefined,
      post: (message) => posted.push(message),
      settle: async () => undefined,
      isVisible: () => true,
    });

    await runtime.receive("https://attacker.example", {
      type: "action",
      action: action(),
    });

    expect(posted).toEqual([]);
  });

  it("returns the matching Action Result with a fresh Snapshot after navigation reload", async () => {
    const storage = new MemoryStorage();
    const navigations: string[] = [];
    const firstDom = new JSDOM(
      '<!doctype html><html lang="ar"><body><h1>الرئيسية</h1></body></html>',
      {
        url: "http://localhost:4000/",
      },
    );
    const firstPosted: unknown[] = [];
    const firstRuntime = new BridgeRuntime({
      document: firstDom.window.document,
      panelOrigin: "http://localhost:4100",
      storage,
      currentUrl: () => firstDom.window.location.href,
      navigate: (url) => navigations.push(url.href),
      post: (message) => firstPosted.push(message),
      settle: async () => undefined,
      isVisible: () => true,
    });

    await firstRuntime.receive("http://localhost:4100", {
      type: "action",
      action: action(),
    });

    expect(navigations).toEqual([
      "http://localhost:4000/c/shoes?type=running&max_price=2000",
    ]);
    expect(firstPosted).toEqual([]);

    const secondDom = new JSDOM(
      '<!doctype html><html lang="ar"><head><title>الأحذية</title></head><body><main><h1>3 منتجات</h1></main></body></html>',
      { url: navigations[0] },
    );
    const secondPosted: unknown[] = [];
    const secondRuntime = new BridgeRuntime({
      document: secondDom.window.document,
      panelOrigin: "http://localhost:4100",
      storage,
      currentUrl: () => secondDom.window.location.href,
      navigate: () => undefined,
      post: (message) => secondPosted.push(message),
      settle: async () => undefined,
      isVisible: () => true,
    });

    secondRuntime.start();

    expect(secondPosted).toEqual([
      {
        type: "action_result",
        result: expect.objectContaining({
          task_id: "task-1",
          action_id: "action-1",
          sequence_number: 1,
          status: "navigated",
          snapshot: expect.objectContaining({
            url: "http://localhost:4000/c/shoes?type=running&max_price=2000",
          }),
        }),
      },
    ]);
  });

  it("rejects a duplicate Action without repeating its DOM effect", async () => {
    const dom = new JSDOM(
      '<!doctype html><html><body><button type="button">Add item</button></body></html>',
      { url: "http://localhost:4000/products" },
    );
    let clicks = 0;
    dom.window.document
      .querySelector("button")!
      .addEventListener("click", () => clicks++);
    const posted: Array<{ type: string; result?: { status: string } }> = [];
    const runtime = new BridgeRuntime({
      document: dom.window.document,
      panelOrigin: "http://localhost:4100",
      storage: new MemoryStorage(),
      currentUrl: () => dom.window.location.href,
      navigate: () => undefined,
      post: (message) => posted.push(message as (typeof posted)[number]),
      settle: async () => undefined,
      isVisible: () => true,
    });
    const button = runtime
      .snapshot()
      .elements.find((element) => element.role === "button")!;
    const click: ClickAction = {
      v: 1,
      type: "click",
      task_id: "task-duplicate",
      action_id: "action-duplicate",
      sequence_number: 1,
      narration: "Adding the item.",
      id: button.id,
    };

    await runtime.receive("http://localhost:4100", {
      type: "action",
      action: click,
    });
    await runtime.receive("http://localhost:4100", {
      type: "action",
      action: click,
    });
    await runtime.receive("http://localhost:4100", {
      type: "action",
      action: { ...click, action_id: "action-stale" },
    });

    expect(clicks).toBe(1);
    expect(posted.map((message) => message.result?.status)).toEqual([
      "ok",
      "stale",
      "stale",
    ]);
  });

  it("rejects a delayed Action from a superseded Shopping Task", async () => {
    const dom = new JSDOM(
      '<!doctype html><html><body><button type="button">Add item</button></body></html>',
      { url: "http://localhost:4000/products" },
    );
    let clicks = 0;
    dom.window.document
      .querySelector("button")!
      .addEventListener("click", () => clicks++);
    const posted: Array<{ type: string; result?: { status: string } }> = [];
    const runtime = new BridgeRuntime({
      document: dom.window.document,
      panelOrigin: "http://localhost:4100",
      storage: new MemoryStorage(),
      currentUrl: () => dom.window.location.href,
      navigate: () => undefined,
      post: (message) => posted.push(message as (typeof posted)[number]),
      settle: async () => undefined,
      isVisible: () => true,
    });
    const button = runtime
      .snapshot()
      .elements.find((element) => element.role === "button")!;
    const taskA: ClickAction = {
      v: 1,
      type: "click",
      task_id: "task-a",
      action_id: "action-a-1",
      sequence_number: 1,
      narration: "Task A.",
      id: button.id,
    };
    const taskB: ClickAction = {
      ...taskA,
      task_id: "task-b",
      action_id: "action-b-1",
      narration: "Task B.",
    };
    const delayedTaskA: ClickAction = {
      ...taskA,
      action_id: "action-a-2",
      sequence_number: 2,
    };

    await runtime.receive("http://localhost:4100", {
      type: "action",
      action: taskA,
    });
    await runtime.receive("http://localhost:4100", {
      type: "action",
      action: taskB,
    });
    await runtime.receive("http://localhost:4100", {
      type: "action",
      action: delayedTaskA,
    });

    expect(clicks).toBe(2);
    expect(posted.map((message) => message.result?.status)).toEqual([
      "ok",
      "ok",
      "stale",
    ]);
  });

  it("rejects an Action after the Panel cancels its Shopping Task", async () => {
    const dom = new JSDOM(
      '<!doctype html><html><body><button type="button">Add item</button></body></html>',
      { url: "http://localhost:4000/products" },
    );
    let clicks = 0;
    dom.window.document
      .querySelector("button")!
      .addEventListener("click", () => clicks++);
    const posted: Array<{ type: string; result?: { status: string } }> = [];
    const runtime = new BridgeRuntime({
      document: dom.window.document,
      panelOrigin: "http://localhost:4100",
      storage: new MemoryStorage(),
      currentUrl: () => dom.window.location.href,
      navigate: () => undefined,
      post: (message) => posted.push(message as (typeof posted)[number]),
      settle: async () => undefined,
      isVisible: () => true,
    });
    const button = runtime
      .snapshot()
      .elements.find((element) => element.role === "button")!;

    await runtime.receive("http://localhost:4100", {
      type: "cancel_task",
      task_id: "task-cancelled",
    });
    await runtime.receive("http://localhost:4100", {
      type: "action",
      action: {
        v: 1,
        type: "click",
        task_id: "task-cancelled",
        action_id: "late-action",
        sequence_number: 1,
        narration: "Too late.",
        id: button.id,
      },
    });

    expect(clicks).toBe(0);
    expect(posted.map((message) => message.result?.status)).toEqual(["stale"]);
  });
});
