import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

import { executeAction } from "../src/actions.js";
import { SnapshotBuilder } from "../src/snapshot.js";
import type { Action } from "../src/types.js";

const identity = {
  v: 1 as const,
  task_id: "task-review",
  action_id: "action-review",
  sequence_number: 1,
  narration: "Safety regression",
};

function fixture(html: string) {
  const dom = new JSDOM(html, { url: "http://localhost:4000/cart" });
  const document = dom.window.document;
  const builder = new SnapshotBuilder(document, { isVisible: () => true });
  builder.build();
  return {
    document,
    builder,
    run: (action: Action) =>
      executeAction(action, {
        builder,
        currentUrl: () => dom.window.location.href,
        storefrontOrigin: dom.window.location.origin,
        navigate: async () => undefined,
        settle: async () => undefined,
      }),
  };
}

describe("Ticket 09/10 review regressions", () => {
  it.each([
    '<base href="https://attacker.example/"><a id="target" href="collect">Offer</a>',
    '<form id="external" action="https://attacker.example/collect"></form><button id="target" form="external">Continue</button>',
    '<base href="https://attacker.example/"><form action="collect"><button id="target">Continue</button></form>',
    '<a id="target" href="http://[invalid">Invalid destination</a>',
    '<form action="/search"><button formaction="https://attacker.example/collect"><span role="button" id="target">Continue</span></button></form>',
  ])("blocks the browser-resolved off-origin destination: %s", async (html) => {
    const { builder, document, run } = fixture(html);
    let clicked = false;
    document.querySelector("#target")!.addEventListener("click", (event) => {
      event.preventDefault();
      clicked = true;
    });
    const target = builder
      .build()
      .elements.find(
        (item) =>
          builder.resolve(item.id)?.element ===
          document.querySelector("#target"),
      )!;
    const result = await run({ ...identity, type: "click", id: target.id });
    expect(result.status).toBe("blocked");
    expect(clicked).toBe(false);
  });

  it.each([
    '<form action="http://localhost:4000/cart/clear" method="post"><button>Empty cart</button></form>',
    '<form id="cart" action="/cart/clear" method="post"></form><button form="cart">Empty cart</button>',
    '<form action="/cart/clear" method="get"><button formmethod="post">Empty cart</button></form>',
    '<form action="/CART/CLEAR/" method="post"><button>Empty cart</button></form>',
    '<form action="/search"><button formaction="/cart/clear" formmethod="post"><span role="button">Empty cart</span></button></form>',
  ])("blocks ordinary clicks on equivalent guarded forms: %s", async (html) => {
    const { builder, document, run } = fixture(html);
    let clicked = false;
    document.querySelector("button")!.addEventListener("click", (event) => {
      event.preventDefault();
      clicked = true;
    });
    const target = builder
      .build()
      .elements.filter((item) => item.role === "button")
      .at(-1)!;
    const result = await run({ ...identity, type: "click", id: target.id });
    expect(result.status).toBe("blocked");
    expect(clicked).toBe(false);
  });

  it("refuses to select a Sensitive Field, including after its identity changes", async () => {
    const { builder, document, run } = fixture(
      '<select name="size"><option>01</option><option>02</option></select>',
    );
    const target = builder
      .build()
      .elements.find((item) => item.role === "combobox")!;
    const select = document.querySelector("select")!;
    select.setAttribute("autocomplete", "cc-exp-month");
    const result = await run({
      ...identity,
      type: "select",
      id: target.id,
      option: "02",
    });
    expect(result.status).toBe("blocked");
    expect(select.value).toBe("01");
  });

  it("does not select a disabled placeholder option", async () => {
    const { builder, document, run } = fixture(
      '<select name="size"><option value="" disabled selected>اختر المقاس</option><option>43</option></select>',
    );
    const target = builder
      .build()
      .elements.find((item) => item.role === "combobox")!;
    const result = await run({
      ...identity,
      type: "select",
      id: target.id,
      option: "اختر المقاس",
    });
    expect(result.status).toBe("not_found");
    expect(document.querySelector("select")!.value).toBe("");
  });

  it.each([
    "section-payment cc-number",
    "section-login one-time-code",
    "current-password",
    "new-password",
  ])("recognizes sensitive autocomplete tokens: %s", (autocomplete) => {
    const { builder } = fixture(
      `<input autocomplete="${autocomplete}" value="private-sentinel">`,
    );
    const snapshot = builder.build();
    expect(snapshot.elements[0].sensitive).toBe(true);
    expect(JSON.stringify(snapshot)).not.toContain("private-sentinel");
  });

  it("excludes sensitive descendants from landmark, label and group text", () => {
    const { builder } = fixture(
      '<main><fieldset><legend>Payment <textarea name="card_number">private-sentinel</textarea></legend><input name="search"></fieldset><select autocomplete="cc-number"><option>private-option</option></select></main>',
    );
    const wire = JSON.stringify(builder.build());
    expect(wire).not.toContain("private-sentinel");
    expect(wire).not.toContain("private-option");
  });

  it("does not reveal sensitive option text through a referenced accessible name", () => {
    const { builder } = fixture(
      '<select autocomplete="cc-number"><option id="saved-card">private-sentinel</option></select><button aria-labelledby="saved-card">Continue</button>',
    );
    expect(JSON.stringify(builder.build())).not.toContain("private-sentinel");
  });
});
