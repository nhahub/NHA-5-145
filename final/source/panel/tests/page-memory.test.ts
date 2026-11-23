import { describe, expect, it } from "vitest";

import { PageMemory, type PageMemoryStorage } from "../src/page-memory.js";

const ORIGIN = "http://localhost:4000";

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  const storage: PageMemoryStorage = {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
  };
  return { storage, data };
}

describe("PageMemory", () => {
  it("opens the home page for a fresh tab", () => {
    const { storage } = memoryStorage();
    expect(new PageMemory(storage, ORIGIN, null).startUrl()).toBe(`${ORIGIN}/`);
  });

  it("reopens the path and query of the latest Storefront Snapshot", () => {
    const { storage } = memoryStorage();
    new PageMemory(storage, ORIGIN, null).remember(
      `${ORIGIN}/p/shoe-01?x=1#top`,
    );
    // A reload builds a new object over the same tab storage.
    expect(new PageMemory(storage, ORIGIN, null).startUrl()).toBe(
      `${ORIGIN}/p/shoe-01?x=1`,
    );
    new PageMemory(storage, ORIGIN, null).remember(`${ORIGIN}/cart`);
    expect(new PageMemory(storage, ORIGIN, null).startUrl()).toBe(
      `${ORIGIN}/cart`,
    );
  });

  it("ignores a Snapshot URL from another origin or a malformed one", () => {
    const { storage, data } = memoryStorage();
    const memory = new PageMemory(storage, ORIGIN, null);
    memory.remember(`${ORIGIN}/p/shoe-01`);
    memory.remember("https://hostile.example/p/shoe-02");
    memory.remember("not a url");
    memory.remember("http://localhost:4000.evil.example/cart");
    expect(memory.startUrl()).toBe(`${ORIGIN}/p/shoe-01`);
    expect(data.size).toBe(1);
  });

  it("falls back to home when the remembered value is foreign or malformed", () => {
    for (const stored of [
      "https://hostile.example/cart",
      "//hostile.example/cart",
      "javascript:alert(1)",
      "not a url",
      "",
    ]) {
      const { storage } = memoryStorage({
        "shopping-copilot.storefront-path": stored,
      });
      expect(new PageMemory(storage, ORIGIN, null).startUrl()).toBe(
        `${ORIGIN}/`,
      );
    }
  });

  it("keeps the SPA variant parameter on the restored page and on home", () => {
    const { storage } = memoryStorage();
    expect(new PageMemory(storage, ORIGIN, "url").startUrl()).toBe(
      `${ORIGIN}/?spa=url`,
    );
    new PageMemory(storage, ORIGIN, "component").remember(
      `${ORIGIN}/p/shoe-01?color=black&spa=url`,
    );
    expect(new PageMemory(storage, ORIGIN, "component").startUrl()).toBe(
      `${ORIGIN}/p/shoe-01?color=black&spa=component`,
    );
  });

  it("ignores an unknown SPA variant", () => {
    const { storage } = memoryStorage();
    expect(new PageMemory(storage, ORIGIN, "bogus").startUrl()).toBe(
      `${ORIGIN}/`,
    );
  });

  it("never throws when storage is unavailable", () => {
    const storage: PageMemoryStorage = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    const memory = new PageMemory(storage, ORIGIN, null);
    expect(() => memory.remember(`${ORIGIN}/cart`)).not.toThrow();
    expect(memory.startUrl()).toBe(`${ORIGIN}/`);
  });
});
