import { JSDOM } from "jsdom";
import { describe, expect, it, vi } from "vitest";

import { executeAction } from "../src/actions.js";
import { SnapshotBuilder } from "../src/snapshot.js";
import type {
  ClickAction,
  NavigateAction,
  SpotlightAction,
  TypeAction,
} from "../src/types.js";

function actionBase() {
  return {
    v: 1 as const,
    task_id: "task-1",
    action_id: "action-1",
    sequence_number: 1,
    narration: "Applying the filters.",
  };
}

describe("executeAction", () => {
  it("does not reuse a previous cart success when the current form is invalid", async () => {
    const dom = new JSDOM(
      '<form action="/cart/items" data-cart-edit="add" data-cart-result="confirmed"><input type="number" min="1" value="0"><button>Add</button></form>',
      { url: "http://localhost:4000/p/shoe-09" },
    );
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });
    const button = builder
      .build()
      .elements.find((item) => item.role === "button")!;
    const result = await executeAction(
      { ...actionBase(), type: "click", id: button.id },
      {
        builder,
        currentUrl: () => dom.window.location.href,
        storefrontOrigin: dom.window.location.origin,
        navigate: async () => undefined,
        settle: async () => undefined,
      },
    );
    expect(result.status).toBe("blocked");
  });
  it("blocks off-origin navigation at the execution boundary", async () => {
    const dom = new JSDOM("<!doctype html><title>Store</title>", {
      url: "http://localhost:4000/",
    });
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });
    const action: NavigateAction = {
      ...actionBase(),
      type: "navigate",
      url: "https://attacker.example/leave",
    };

    const result = await executeAction(action, {
      builder,
      currentUrl: () => "http://localhost:4000/",
      storefrontOrigin: "http://localhost:4000",
      navigate: async () => undefined,
      settle: async () => undefined,
    });

    expect(result.status).toBe("blocked");
    expect(result.snapshot.url).toBe("http://localhost:4000/");
  });

  it("does not adopt an attacker page as the Storefront origin", async () => {
    const dom = new JSDOM("<!doctype html><title>Escaped</title>", {
      url: "https://attacker.example/",
    });
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });
    const navigate = vi.fn();
    const action: NavigateAction = {
      ...actionBase(),
      type: "navigate",
      url: "/collect",
    };

    const result = await executeAction(action, {
      builder,
      currentUrl: () => "https://attacker.example/",
      storefrontOrigin: "http://localhost:4000",
      navigate,
      settle: async () => undefined,
    });

    expect(result.status).toBe("blocked");
    expect(navigate).not.toHaveBeenCalled();
  });

  it("blocks a click on an off-origin Storefront link", async () => {
    const dom = new JSDOM(
      '<a href="https://attacker.example/collect">Special offer</a>',
      { url: "http://localhost:4000/" },
    );
    const link = dom.window.document.querySelector("a")!;
    const clicked = vi.fn();
    link.addEventListener("click", clicked);
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });

    const result = await executeAction(
      { ...actionBase(), type: "click", id: builder.build().elements[0].id },
      {
        builder,
        currentUrl: () => "http://localhost:4000/",
        storefrontOrigin: "http://localhost:4000",
        navigate: async () => undefined,
        settle: async () => undefined,
      },
    );

    expect(result.status).toBe("blocked");
    expect(clicked).not.toHaveBeenCalled();
  });

  it("blocks form submission to an off-origin destination before typing", async () => {
    const dom = new JSDOM(
      '<form action="https://attacker.example/collect"><input name="search"></form>',
      { url: "http://localhost:4000/" },
    );
    const input = dom.window.document.querySelector("input")!;
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });

    const result = await executeAction(
      {
        ...actionBase(),
        type: "type",
        id: builder.build().elements[0].id,
        text: "private search",
        submit: true,
      },
      {
        builder,
        currentUrl: () => "http://localhost:4000/",
        storefrontOrigin: "http://localhost:4000",
        navigate: async () => undefined,
        settle: async () => undefined,
      },
    );

    expect(result.status).toBe("blocked");
    expect(input.value).toBe("");
  });

  it("rechecks field sensitivity immediately before typing", async () => {
    const dom = new JSDOM('<input id="target" name="search" value="">', {
      url: "http://localhost:4000/",
    });
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });
    const id = builder.build().elements[0].id;
    const input = dom.window.document.querySelector("input")!;
    input.type = "password";

    const result = await executeAction(
      { ...actionBase(), type: "type", id, text: "secret", submit: false },
      {
        builder,
        currentUrl: () => "http://localhost:4000/",
        storefrontOrigin: "http://localhost:4000",
        navigate: async () => undefined,
        settle: async () => undefined,
      },
    );

    expect(result.status).toBe("blocked");
    expect(input.value).toBe("");
    expect(result.snapshot.elements[0]).not.toHaveProperty("value");
  });

  it("blocks a disabled purchase control instead of reporting success", async () => {
    const dom = new JSDOM(
      '<button disabled data-testid="add-to-cart">غير متاح</button>',
      { url: "http://localhost:4000/p/shoe-05" },
    );
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });
    const button = dom.window.document.querySelector("button")!;
    const clicked = vi.fn();
    button.addEventListener("click", clicked);
    const action: ClickAction = {
      ...actionBase(),
      type: "click",
      id: builder.build().elements[0].id,
    };

    const result = await executeAction(action, {
      builder,
      currentUrl: () => "http://localhost:4000/p/shoe-05",
      storefrontOrigin: "http://localhost:4000",
      navigate: async () => undefined,
      settle: async () => undefined,
    });

    expect(result.status).toBe("blocked");
    expect(clicked).not.toHaveBeenCalled();
  });

  it("blocks a target hidden after its snapshot was taken", async () => {
    const dom = new JSDOM(
      '<div><button type="button">تطبيق الفلاتر</button></div>',
      {
        url: "http://localhost:4000/c/shoes",
      },
    );
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: (element) => !element.closest("[hidden]"),
    });
    const button = dom.window.document.querySelector("button")!;
    const clicked = vi.fn();
    button.addEventListener("click", clicked);
    const id = builder
      .build()
      .elements.find((item) => item.role === "button")!.id;
    button.parentElement!.hidden = true;

    const outcome = await executeAction(
      { ...actionBase(), type: "click", id },
      {
        builder,
        currentUrl: () => "http://localhost:4000/c/shoes",
        storefrontOrigin: "http://localhost:4000",
        navigate: async () => undefined,
        settle: async () => undefined,
      },
    );

    expect(outcome.status).toBe("blocked");
    expect(clicked).not.toHaveBeenCalled();
  });

  it("blocks a control when its parent becomes inert or aria-disabled", async () => {
    const dom = new JSDOM(
      '<div><button type="button">تحميل المزيد</button></div>',
      {
        url: "http://localhost:4000/c/shoes",
      },
    );
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });
    const button = dom.window.document.querySelector("button")!;
    const parent = button.parentElement!;
    const clicked = vi.fn();
    button.addEventListener("click", clicked);
    const id = builder
      .build()
      .elements.find((item) => item.role === "button")!.id;
    for (const attribute of ["inert", "aria-disabled"] as const) {
      parent.setAttribute(attribute, "true");
      const outcome = await executeAction(
        { ...actionBase(), type: "click", id },
        {
          builder,
          currentUrl: () => "http://localhost:4000/c/shoes",
          storefrontOrigin: "http://localhost:4000",
          navigate: async () => undefined,
          settle: async () => undefined,
        },
      );
      expect(outcome.status).toBe("blocked");
      parent.removeAttribute(attribute);
    }
    expect(clicked).not.toHaveBeenCalled();
  });

  it("refuses to type into a Sensitive Field", async () => {
    const dom = new JSDOM(
      `<!doctype html><html><body>
      <label for="card">Card number</label>
      <input id="card" autocomplete="cc-number" value="">
    </body></html>`,
      { url: "http://localhost:4000/checkout" },
    );
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });
    const sensitive = builder.build().elements[0];
    const action: TypeAction = {
      ...actionBase(),
      type: "type",
      id: sensitive.id,
      text: "4111111111111111",
      submit: false,
    };

    const result = await executeAction(action, {
      builder,
      currentUrl: () => "http://localhost:4000/checkout",
      storefrontOrigin: "http://localhost:4000",
      navigate: async () => undefined,
      settle: async () => undefined,
    });

    expect(result.status).toBe("blocked");
    expect(dom.window.document.querySelector("input")?.value).toBe("");
  });

  it("visibly spotlights the target and smoothly centers it in view", async () => {
    const dom = new JSDOM(
      '<!doctype html><html><body><a href="/cart">Cart</a></body></html>',
      { url: "http://localhost:4000/" },
    );
    const link = dom.window.document.querySelector("a")!;
    const scrollIntoView = vi.fn();
    Object.defineProperty(link, "scrollIntoView", { value: scrollIntoView });
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });
    const action: SpotlightAction = {
      ...actionBase(),
      type: "spotlight",
      id: builder.build().elements[0].id,
      message: "Your cart is here.",
    };

    const result = await executeAction(action, {
      builder,
      currentUrl: () => "http://localhost:4000/",
      storefrontOrigin: "http://localhost:4000",
      navigate: async () => undefined,
      settle: async () => undefined,
    });

    expect(result.status).toBe("ok");
    expect(link.getAttribute("data-copilot-spotlight")).toBe(
      "Your cart is here.",
    );
    expect(link.style.outline).toContain("solid");
    expect(link.style.boxShadow).not.toBe("");
    expect(scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "center",
      inline: "center",
    });
  });

  it("uses immediate scrolling when reduced motion is preferred", async () => {
    const dom = new JSDOM(
      '<!doctype html><html><body><a href="/cart">Cart</a></body></html>',
      { url: "http://localhost:4000/" },
    );
    Object.defineProperty(dom.window, "matchMedia", {
      value: () => ({ matches: true }),
    });
    const link = dom.window.document.querySelector("a")!;
    const scrollIntoView = vi.fn();
    Object.defineProperty(link, "scrollIntoView", { value: scrollIntoView });
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });
    const action: SpotlightAction = {
      ...actionBase(),
      type: "spotlight",
      id: builder.build().elements[0].id,
      message: "Your cart is here.",
    };

    await executeAction(action, {
      builder,
      currentUrl: () => "http://localhost:4000/",
      storefrontOrigin: "http://localhost:4000",
      navigate: async () => undefined,
      settle: async () => undefined,
    });

    expect(scrollIntoView).toHaveBeenCalledWith({
      behavior: "instant",
      block: "center",
      inline: "center",
    });
  });

  it("refuses to type into a login identifier", async () => {
    const dom = new JSDOM(
      `<!doctype html><html><body>
      <form><input name="username" type="email" autocomplete="username" value="">
      <input name="password" type="password" value=""></form>
      </body></html>`,
      { url: "http://localhost:4000/login" },
    );
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });
    const loginIdentifier = builder.build().elements[0];
    const action: TypeAction = {
      ...actionBase(),
      type: "type",
      id: loginIdentifier.id,
      text: "shopper@example.test",
      submit: false,
    };

    const result = await executeAction(action, {
      builder,
      currentUrl: () => "http://localhost:4000/login",
      storefrontOrigin: "http://localhost:4000",
      navigate: async () => undefined,
      settle: async () => undefined,
    });

    expect(result.status).toBe("blocked");
    expect(
      dom.window.document.querySelector<HTMLInputElement>(
        '[autocomplete="username"]',
      )?.value,
    ).toBe("");
  });

  it("refuses to type into a one-time-code field", async () => {
    const dom = new JSDOM(
      `<!doctype html><html><body>
      <input name="code" autocomplete="one-time-code" value="">
      </body></html>`,
      { url: "http://localhost:4000/login/verify" },
    );
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    });
    const oneTimeCode = builder.build().elements[0];
    const action: TypeAction = {
      ...actionBase(),
      type: "type",
      id: oneTimeCode.id,
      text: "123456",
      submit: false,
    };

    const result = await executeAction(action, {
      builder,
      currentUrl: () => "http://localhost:4000/login/verify",
      storefrontOrigin: "http://localhost:4000",
      navigate: async () => undefined,
      settle: async () => undefined,
    });

    expect(result.status).toBe("blocked");
    expect(dom.window.document.querySelector("input")?.value).toBe("");
  });

  it("returns a fresh filtered Snapshot after same-origin navigation", async () => {
    const dom = new JSDOM(
      '<!doctype html><html lang="ar"><title>الرئيسية</title><body></body></html>',
      {
        url: "http://localhost:4000/",
      },
    );
    let currentUrl = "http://localhost:4000/";
    const builder = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
      url: () => currentUrl,
    });
    const action: NavigateAction = {
      ...actionBase(),
      type: "navigate",
      url: "/c/shoes?type=running&max_price=2000",
    };

    const result = await executeAction(action, {
      builder,
      currentUrl: () => currentUrl,
      storefrontOrigin: "http://localhost:4000",
      navigate: async (url) => {
        currentUrl = url.href;
        dom.window.document.title = "الأحذية";
        dom.window.document.body.innerHTML = "<main><h1>3 منتجات</h1></main>";
      },
      settle: async () => undefined,
    });

    expect(result.status).toBe("navigated");
    expect(result.snapshot.url).toContain("type=running&max_price=2000");
    expect(result.snapshot.elements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ role: "heading", name: "3 منتجات" }),
      ]),
    );
  });
});
