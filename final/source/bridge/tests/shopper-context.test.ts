import { JSDOM } from "jsdom";
import { expect, it } from "vitest";
import { matchesShopperContext } from "../src/shopper-context.js";

it("rejects actions from a previous or missing document shopper context", () => {
  const dom = new JSDOM(
    '<meta name="copilot-context" content="' + "a".repeat(64) + '">',
  );
  expect(matchesShopperContext(dom.window.document, "a".repeat(64))).toBe(true);
  expect(matchesShopperContext(dom.window.document, "b".repeat(64))).toBe(
    false,
  );
  expect(matchesShopperContext(dom.window.document, undefined)).toBe(false);
  dom.window.document.querySelector("meta")!.remove();
  expect(matchesShopperContext(dom.window.document, "")).toBe(false);
  dom.window.close();
});
