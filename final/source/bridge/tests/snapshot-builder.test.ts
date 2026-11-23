import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

import { SnapshotBuilder } from "../src/snapshot.js";
import { parseSnapshot } from "../src/types.js";

describe("SnapshotBuilder", () => {
  it("emits a valid wire snapshot after fractional browser scrolling", () => {
    const dom = new JSDOM("<button>Add</button>", {
      url: "http://localhost:4000/p/clothing-02",
    });
    Object.defineProperty(dom.window, "scrollY", { value: 211.42857360839844 });
    const snapshot = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    }).build();
    expect(() => parseSnapshot(snapshot)).not.toThrow();
  });
  it("marks controls disabled by an ancestor before the Agent plans an Action", () => {
    const dom = new JSDOM(
      '<fieldset disabled><button>Submit</button></fieldset><div aria-disabled="true"><button>Continue</button></div>',
      { url: "http://localhost:4000/cart" },
    );
    const buttons = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    })
      .build()
      .elements.filter((item) => item.role === "button");
    expect(buttons).toEqual([
      expect.objectContaining({ name: "Submit", disabled: true }),
      expect.objectContaining({ name: "Continue", disabled: true }),
    ]);
  });
  it("exposes form actions only on submit buttons, not size swatches", () => {
    const dom = new JSDOM(
      '<form action="/cart/items"><button type="button" aria-label="مقاس 43">43</button><button type="submit">أضف إلى السلة</button></form>',
      { url: "http://localhost:4000/p/shoe-09" },
    );
    const buttons = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    })
      .build()
      .elements.filter((item) => item.role === "button");
    expect(
      buttons.find((item) => item.name === "مقاس 43")?.form_action,
    ).toBeUndefined();
    expect(
      buttons.find((item) => item.name === "أضف إلى السلة")?.form_action,
    ).toBe("/cart/items");
  });
  it("offers only selectable options, not a disabled placeholder", () => {
    const dom = new JSDOM(
      '<label for="s">المقاس</label><select id="s" required><option value="" disabled selected>اختر المقاس</option><option>42</option><option>43</option></select>',
      { url: "http://localhost:4000/p/shoe-09" },
    );
    const select = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    })
      .build()
      .elements.find((item) => item.role === "combobox");
    expect(select).toEqual(
      expect.objectContaining({
        name: "المقاس",
        value: "",
        options: ["42", "43"],
      }),
    );
  });
  it("describes Arabic category controls using their accessible names", () => {
    const dom = new JSDOM(
      `<!doctype html><html lang="ar"><head><title>الأحذية</title></head><body>
      <header><a href="/cart">السلة (0)</a></header>
      <main>
        <form aria-label="فلترة الأحذية">
          <fieldset><legend>نوع الحذاء</legend>
            <label><input type="radio" name="type" value="running"> جري</label>
          </fieldset>
          <label for="max-price">أقصى سعر</label>
          <input id="max-price" name="max_price" value="">
          <button>تطبيق الفلاتر</button>
        </form>
      </main>
    </body></html>`,
      { url: "http://localhost:4000/c/shoes" },
    );

    const snapshot = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
      viewport: { w: 390, h: 844, scrollY: 0 },
    }).build();

    expect(snapshot).toMatchObject({
      v: 1,
      url: "http://localhost:4000/c/shoes",
      title: "الأحذية",
      lang: "ar",
      truncated: false,
    });
    expect(snapshot.elements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          role: "link",
          name: "السلة (0)",
          region: "header",
        }),
        expect.objectContaining({
          role: "radio",
          name: "جري",
          group: "نوع الحذاء",
        }),
        expect.objectContaining({
          role: "textbox",
          name: "أقصى سعر",
          value: "",
        }),
        expect.objectContaining({ role: "button", name: "تطبيق الفلاتر" }),
      ]),
    );
  });

  it("represents a Sensitive Field without collecting its value or state", () => {
    const dom = new JSDOM(
      `<!doctype html><html><body>
      <label for="card">Card number</label>
      <input id="card" name="card_number" autocomplete="cc-number" value="4111111111111111">
    </body></html>`,
      { url: "http://localhost:4000/checkout" },
    );

    const snapshot = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
      viewport: { w: 1280, h: 720, scrollY: 0 },
    }).build();

    expect(snapshot.elements).toEqual([
      expect.objectContaining({
        role: "textbox",
        name: "Sensitive field",
        sensitive: true,
      }),
    ]);
    expect(snapshot.elements[0]).not.toHaveProperty("value");
  });

  it("excludes a login identifier value when autocomplete identifies it", () => {
    const dom = new JSDOM(
      `<!doctype html><html><body>
      <form><input name="username" type="email" autocomplete="username" value="shopper@example.test">
      <input name="password" type="password" value="private-password"></form>
      </body></html>`,
      { url: "http://localhost:4000/login" },
    );

    const snapshot = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    }).build();

    expect(snapshot.elements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ role: "textbox", sensitive: true }),
        expect.objectContaining({ role: "textbox", sensitive: true }),
      ]),
    );
    expect(JSON.stringify(snapshot)).not.toContain("shopper@example.test");
    expect(JSON.stringify(snapshot)).not.toContain("private-password");
    expect(
      snapshot.elements.filter((element) => element.sensitive),
    ).toHaveLength(2);
  });

  it("recognizes login email fields without treating newsletter or search email as sensitive", () => {
    const dom = new JSDOM(
      `<!doctype html><html><body>
      <form id="sign-in"><label for="login-email">Login email</label>
        <input id="login-email" type="email" name="email" value="login@example.test">
        <input type="password" value="private-password"></form>
      <form id="newsletter"><label for="newsletter-email">Newsletter email</label>
        <input id="newsletter-email" type="email" name="email" value="news@example.test"></form>
      <form role="search"><label for="search-email">Email search</label>
        <input id="search-email" type="email" name="email" value="query@example.test"></form>
      </body></html>`,
      { url: "http://localhost:4000/account/login" },
    );

    const snapshot = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    }).build();
    expect(snapshot.elements[0]).toMatchObject({ sensitive: true });
    expect(snapshot.elements[0]).not.toHaveProperty("value");
    expect(snapshot.elements.at(-1)).toMatchObject({
      value: "query@example.test",
    });
    expect(JSON.stringify(snapshot)).not.toContain("login@example.test");
    expect(JSON.stringify(snapshot)).toContain("news@example.test");
  });

  it("recognizes a plain-text username in a login form", () => {
    const dom = new JSDOM(
      `<!doctype html><html><body>
      <form><label for="account-name">Username</label>
        <input id="account-name" name="username" value="shopper-name">
        <input type="password" value="private-password"></form>
      </body></html>`,
      { url: "http://localhost:4000/login" },
    );

    const snapshot = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    }).build();

    expect(snapshot.elements[0]).toMatchObject({ sensitive: true });
    expect(snapshot.elements[0]).not.toHaveProperty("value");
    expect(JSON.stringify(snapshot)).not.toContain("shopper-name");
  });

  it("excludes one-time-code values and their input state", () => {
    const dom = new JSDOM(
      `<!doctype html><html><body>
      <label for="otp">Verification code</label>
      <input id="otp" name="code" autocomplete="one-time-code" value="123456">
      </body></html>`,
      { url: "http://localhost:4000/login/verify" },
    );

    const snapshot = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    }).build();

    expect(snapshot.elements).toEqual([
      expect.objectContaining({
        role: "textbox",
        name: "Sensitive field",
        sensitive: true,
      }),
    ]);
    expect(snapshot.elements[0]).not.toHaveProperty("value");
    expect(snapshot.elements[0]).not.toHaveProperty("disabled");
    expect(JSON.stringify(snapshot)).not.toContain("123456");
  });

  it("does not expose a secret repeated in a Sensitive Field label", () => {
    const secret = "4111111111111111";
    const dom = new JSDOM(
      `<!doctype html><input autocomplete="cc-number" aria-label="Card ${secret}" value="${secret}">`,
      { url: "http://localhost:4000/checkout" },
    );

    const snapshot = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    }).build();

    expect(snapshot.elements[0]).toMatchObject({ sensitive: true });
    expect(JSON.stringify(snapshot)).not.toContain(secret);
  });

  it("redacts Sensitive Field values carried by a textarea", () => {
    const dom = new JSDOM(
      '<textarea name="card_number">4111111111111111</textarea>',
      { url: "http://localhost:4000/checkout" },
    );

    const snapshot = new SnapshotBuilder(dom.window.document, {
      isVisible: () => true,
    }).build();

    expect(snapshot.elements[0]).toMatchObject({ sensitive: true });
    expect(JSON.stringify(snapshot)).not.toContain("4111111111111111");
  });
});
