/** Remembers the Storefront page of this browser tab so a Panel reload reopens it. */

export interface PageMemoryStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const PATH_KEY = "shopping-copilot.storefront-path";
const SPA_VARIANTS = new Set(["url", "component", "off"]);

export class PageMemory {
  readonly #storage: PageMemoryStorage;
  readonly #origin: string;
  readonly #spaVariant: string | null;

  constructor(
    storage: PageMemoryStorage,
    storefrontOrigin: string,
    spaVariant: string | null,
  ) {
    this.#storage = storage;
    this.#origin = storefrontOrigin;
    this.#spaVariant =
      spaVariant !== null && SPA_VARIANTS.has(spaVariant) ? spaVariant : null;
  }

  /** Keep path+query of a Snapshot URL, only when it is on the Storefront origin. */
  remember(snapshotUrl: unknown): void {
    const path = this.#pathOf(snapshotUrl);
    if (path === null) return;
    try {
      this.#storage.setItem(PATH_KEY, path);
    } catch {
      // Storage may be blocked; the next load simply opens home.
    }
  }

  /** The URL the Storefront frame should open: the remembered page, else home. */
  startUrl(): string {
    let stored: string | null = null;
    try {
      stored = this.#storage.getItem(PATH_KEY);
    } catch {
      stored = null;
    }
    const usable =
      stored !== null && /^\/(?![/\\])/.test(stored) ? stored : "/";
    const url = new URL(`${this.#origin}${usable}`);
    if (url.origin !== this.#origin) url.href = `${this.#origin}/`;
    url.searchParams.delete("spa");
    if (this.#spaVariant !== null)
      url.searchParams.set("spa", this.#spaVariant);
    return url.href;
  }

  #pathOf(value: unknown): string | null {
    if (typeof value !== "string") return null;
    let url: URL;
    try {
      url = new URL(value);
    } catch {
      return null;
    }
    if (url.origin !== this.#origin) return null;
    // The SPA variant belongs to the Panel URL, never to the remembered page.
    url.searchParams.delete("spa");
    return `${url.pathname}${url.search}`;
  }
}
