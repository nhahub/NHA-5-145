import { JSDOM } from "jsdom";
import { expect, it } from "vitest";
import { BridgeRuntime } from "../src/runtime.js";
import { executeAction } from "../src/actions.js";
import { SnapshotBuilder } from "../src/snapshot.js";

it("publishes committed choices immediately but withholds optimistic state until settled", async () => {
  const dom = new JSDOM('<input aria-label="Quantity" value="1">', {
    url: "http://localhost:4000/cart",
  });
  const posted: unknown[] = [];
  let release!: () => void;
  const settling = new Promise<void>((resolve) => {
    release = resolve;
  });
  const runtime = new BridgeRuntime({
    document: dom.window.document,
    panelOrigin: "http://localhost:4100",
    storage: dom.window.sessionStorage,
    currentUrl: () => dom.window.location.href,
    navigate: () => undefined,
    post: (message) => posted.push(message),
    settle: () => settling,
    isVisible: () => true,
  });
  try {
    runtime.start();
    posted.length = 0;
    const input = dom.window.document.querySelector("input")!;
    input.value = "3";
    input.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    expect(posted).toHaveLength(1);
    expect(JSON.stringify(posted[0])).toContain('"value":"3"');
    dom.window.document.documentElement.setAttribute(
      "data-cart-pending",
      "true",
    );
    input.value = "7";
    input.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    expect(posted).toHaveLength(1);
    input.value = "3";
    dom.window.document.documentElement.removeAttribute("data-cart-pending");
    release();
    await expect.poll(() => posted.length).toBe(2);
    expect(JSON.stringify(posted[1])).toContain('"value":"3"');
  } finally {
    release();
    runtime.stop();
    dom.window.close();
  }
});

it("publishes settled history/DOM changes without a document reload", async () => {
  const dom = new JSDOM("<main><h1>Home</h1></main>", {
    url: "http://localhost:4000/",
  });
  const posted: unknown[] = [];
  const runtime = new BridgeRuntime({
    document: dom.window.document,
    panelOrigin: "http://localhost:4100",
    storage: dom.window.sessionStorage,
    currentUrl: () => dom.window.location.href,
    navigate: () => undefined,
    post: (message) => posted.push(message),
    settle: async () => undefined,
    isVisible: () => true,
  });
  try {
    runtime.start();
    dom.window.history.pushState({}, "", "/account");
    dom.window.document.querySelector("main")!.innerHTML = "<h1>Account</h1>";
    await expect.poll(() => JSON.stringify(posted.at(-1))).toContain("Account");
    expect(JSON.stringify(posted.at(-1))).toContain("/account");
  } finally {
    runtime.stop();
    dom.window.close();
  }
});

it("returns one result for same-document navigation and does not reexecute a duplicate", async () => {
  const dom = new JSDOM("<main>Home</main>", { url: "http://localhost:4000/" });
  const posted: unknown[] = [];
  let navigations = 0;
  const runtime = new BridgeRuntime({
    document: dom.window.document,
    panelOrigin: "http://localhost:4100",
    storage: dom.window.sessionStorage,
    currentUrl: () => dom.window.location.href,
    navigate: (url) => {
      navigations++;
      dom.window.history.pushState({}, "", url);
    },
    post: (message) => posted.push(message),
    settle: async () => undefined,
    isVisible: () => true,
  });
  const action = {
    v: 1,
    type: "navigate",
    task_id: "spa",
    action_id: "nav",
    sequence_number: 1,
    narration: "Open",
    url: "/cart",
  };
  try {
    runtime.start();
    await runtime.receive("http://localhost:4100", { type: "action", action });
    expect(posted).toContainEqual(
      expect.objectContaining({
        type: "action_result",
        result: expect.objectContaining({
          status: "navigated",
          action_id: "nav",
        }),
      }),
    );
    expect(
      dom.window.sessionStorage.getItem("shopping-copilot.pending-navigation"),
    ).toBeNull();
    await runtime.receive("http://localhost:4100", { type: "action", action });
    expect(navigations).toBe(1);
  } finally {
    runtime.stop();
    dom.window.close();
  }
});

it("does not report success when a controlled input rejects the assigned value", async () => {
  const dom = new JSDOM('<input aria-label="Quantity" value="1">', {
    url: "http://localhost:4000/cart",
  });
  const builder = new SnapshotBuilder(dom.window.document, {
    isVisible: () => true,
  });
  const id = builder.build().elements.find((e) => e.role === "textbox")!.id;
  const result = await executeAction(
    {
      v: 1,
      type: "type",
      task_id: "t",
      action_id: "a",
      sequence_number: 1,
      narration: "Change",
      id,
      text: "8",
      submit: false,
    },
    {
      builder,
      currentUrl: () => dom.window.location.href,
      storefrontOrigin: dom.window.location.origin,
      navigate: async () => undefined,
      settle: async () => {
        dom.window.document.querySelector("input")!.value = "1";
      },
    },
  );
  expect(result.status).toBe("blocked");
  dom.window.close();
});
