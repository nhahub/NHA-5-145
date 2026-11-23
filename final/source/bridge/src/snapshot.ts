import type { Snapshot, SnapshotElement, Viewport } from "./types.js";
import { recordEvaluationTiming } from "./evaluation-metrics.js";

const SNAPSHOT_BUDGET_BYTES = 12_000;
const INTERACTIVE_ROLES = new Set([
  "link",
  "button",
  "textbox",
  "searchbox",
  "checkbox",
  "radio",
  "combobox",
  "listbox",
  "option",
  "heading",
  "tab",
  "menuitem",
  "banner",
  "navigation",
  "main",
  "contentinfo",
  "dialog",
  "status",
]);

export interface SnapshotBuilderOptions {
  isVisible?: (element: Element) => boolean;
  url?: () => string;
  viewport?: Viewport;
}

export interface RegisteredElement {
  element: Element;
  sensitive: boolean;
}

function compactText(value: string | null | undefined): string {
  return (value ?? "").replace(/\s+/g, " ").trim().slice(0, 80);
}

function textWithoutFieldValues(node: Node): string {
  if (node.nodeType === node.TEXT_NODE) return node.textContent ?? "";
  if (node.nodeType === node.ELEMENT_NODE) {
    const element = node as Element;
    if (["input", "textarea", "select"].includes(element.tagName.toLowerCase()))
      return "";
    if (element.closest("select") !== null) return "";
  }
  return [...node.childNodes].map(textWithoutFieldValues).join("");
}

function implicitRole(element: Element): string | undefined {
  const tag = element.tagName.toLowerCase();
  if (tag === "a" && element.hasAttribute("href")) return "link";
  if (tag === "button") return "button";
  if (tag === "summary") return "button";
  if (tag === "textarea") return "textbox";
  if (tag === "select")
    return element.hasAttribute("multiple") ? "listbox" : "combobox";
  if (tag === "option") return "option";
  if (/^h[1-6]$/.test(tag)) return "heading";
  if (tag === "header") return "banner";
  if (tag === "nav") return "navigation";
  if (tag === "main") return "main";
  if (tag === "footer") return "contentinfo";
  if (tag === "dialog") return "dialog";
  if (tag !== "input") return undefined;

  const type = (element.getAttribute("type") ?? "text").toLowerCase();
  if (type === "checkbox") return "checkbox";
  if (type === "radio") return "radio";
  if (type === "button" || type === "submit" || type === "reset")
    return "button";
  if (type === "search") return "searchbox";
  if (["hidden", "file", "image"].includes(type)) return undefined;
  return "textbox";
}

function elementRole(element: Element): string | undefined {
  return element.getAttribute("role") ?? implicitRole(element);
}

function labelledByText(element: Element): string {
  const ids = element.getAttribute("aria-labelledby")?.split(/\s+/) ?? [];
  return compactText(
    ids
      .map((id) => {
        const label = element.ownerDocument.getElementById(id);
        return label === null ? "" : textWithoutFieldValues(label);
      })
      .join(" "),
  );
}

function labelText(element: Element): string {
  if (!(element instanceof element.ownerDocument.defaultView!.HTMLElement))
    return "";
  const labels =
    "labels" in element
      ? (element.labels as NodeListOf<HTMLLabelElement> | null)
      : null;
  return compactText(
    labels ? [...labels].map(textWithoutFieldValues).join(" ") : "",
  );
}

function accessibleName(element: Element): string {
  const textContent =
    element.tagName.toLowerCase() === "option" && !isSensitiveField(element, "")
      ? element.textContent
      : textWithoutFieldValues(element);
  return (
    labelledByText(element) ||
    compactText(element.getAttribute("aria-label")) ||
    labelText(element) ||
    compactText(textContent) ||
    compactText(element.getAttribute("alt")) ||
    compactText(element.getAttribute("title")) ||
    compactText(element.getAttribute("placeholder"))
  );
}

function defaultVisibility(element: Element): boolean {
  if (
    !element.isConnected ||
    element.closest('[hidden], [aria-hidden="true"], [inert]') ||
    (element.closest("dialog") !== null &&
      !element.closest("dialog")!.hasAttribute("open"))
  )
    return false;
  const disclosure = element.closest("details:not([open])");
  if (
    disclosure !== null &&
    element !== disclosure.querySelector(":scope > summary")
  )
    return false;
  const view = element.ownerDocument.defaultView;
  if (view === null) return false;
  for (
    let node: Element | null = element;
    node !== null;
    node = node.parentElement
  ) {
    const style = view.getComputedStyle(node);
    if (style.display === "none" || style.visibility === "hidden") return false;
  }
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

function nearestRegion(element: Element): string | undefined {
  const landmark = element.closest(
    "header, nav, main, footer, dialog, [role=dialog]",
  );
  if (landmark === null || landmark === element) return undefined;
  return landmark.getAttribute("role") ?? landmark.tagName.toLowerCase();
}

function nearestGroup(element: Element): string | undefined {
  const fieldset = element.closest("fieldset");
  if (fieldset !== null) {
    const legend = fieldset.querySelector("legend");
    return compactText(legend === null ? "" : textWithoutFieldValues(legend));
  }
  const group = element.closest('[role="group"], [role="radiogroup"]');
  return group === null ? undefined : accessibleName(group);
}

function isSensitiveField(element: Element, name: string): boolean {
  if (element.tagName.toLowerCase() === "option") {
    const select = element.closest("select");
    return select !== null && isSensitiveField(select, accessibleName(select));
  }
  if (!["input", "textarea", "select"].includes(element.tagName.toLowerCase()))
    return false;
  const type = (element.getAttribute("type") ?? "").toLowerCase();
  const autocomplete = (element.getAttribute("autocomplete") ?? "")
    .toLowerCase()
    .split(/\s+/);
  const identity = [
    element.getAttribute("name"),
    element.getAttribute("id"),
    element.getAttribute("aria-label"),
    element.getAttribute("placeholder"),
    name,
  ]
    .filter(Boolean)
    .join(" ");
  const loginIdentifierName =
    /(?:^|[^a-z0-9])(?:e-?mail(?:[-_ ]address)?|user(?:name|_name)?|login(?:[-_ ]id)?)(?:$|[^a-z0-9])/i.test(
      identity,
    );
  const form = element.closest("form");
  const formIdentity =
    form === null
      ? ""
      : [
          form.getAttribute("id"),
          form.getAttribute("name"),
          form.getAttribute("aria-label"),
          form.getAttribute("action"),
        ]
          .filter(Boolean)
          .join(" ");
  const loginForm =
    form !== null &&
    (form.querySelector('input[type="password"]') !== null ||
      /(?:^|[^a-z0-9])(?:log[-_ ]?in|sign[-_ ]?in|auth(?:entication)?)(?:$|[^a-z0-9])/i.test(
        formIdentity,
      ));
  return (
    type === "password" ||
    autocomplete.some(
      (token) =>
        token.startsWith("cc-") ||
        [
          "one-time-code",
          "username",
          "current-password",
          "new-password",
        ].includes(token),
    ) ||
    /card|cvv|cvc|expir/i.test(identity) ||
    (["", "email", "text"].includes(type) && loginIdentifierName && loginForm)
  );
}

function optionalState(
  element: Element,
  role: string,
): Partial<SnapshotElement> {
  const state: Partial<SnapshotElement> = {};
  if (role === "link") state.href = element.getAttribute("href") ?? undefined;
  if (role === "button") {
    const form = element.closest("form");
    const buttonType = (element.getAttribute("type") ?? "submit").toLowerCase();
    if (form !== null && buttonType === "submit") {
      state.form_action =
        element.getAttribute("formaction") ??
        form.getAttribute("action") ??
        undefined;
    }
    if (element.hasAttribute("data-guarded-mutation")) {
      const revision = element.getAttribute("data-cart-revision");
      if (revision !== null && /^\d+$/.test(revision))
        state.mutation_state = `cart:${revision}`;
    }
  }
  if (element instanceof element.ownerDocument.defaultView!.HTMLInputElement) {
    state.value = element.value;
    if (role === "checkbox" || role === "radio")
      state.checked = element.checked;
    state.disabled = element.disabled;
  } else if (
    element instanceof element.ownerDocument.defaultView!.HTMLSelectElement
  ) {
    state.value = element.value;
    // Disabled options (such as a "choose…" placeholder) cannot be selected.
    state.options = [...element.options]
      .filter((option) => !option.disabled)
      .map((option) => compactText(option.textContent));
    state.disabled = element.disabled;
  } else if (
    element instanceof element.ownerDocument.defaultView!.HTMLButtonElement
  ) {
    state.disabled = element.disabled;
  }
  if (
    element.matches(":disabled") ||
    element.closest('[aria-disabled="true"], [inert], fieldset[disabled]')
  )
    state.disabled = true;
  if (role === "heading") state.level = Number(element.tagName.slice(1));
  return state;
}

export class SnapshotBuilder {
  isBusy(): boolean {
    return documentIsBusy(this.#document);
  }
  readonly #document: Document;
  readonly #options: SnapshotBuilderOptions;
  readonly #ids = new WeakMap<Element, number>();
  readonly #elements = new Map<number, RegisteredElement>();
  #nextId = 1;

  constructor(document: Document, options: SnapshotBuilderOptions = {}) {
    this.#document = document;
    this.#options = options;
  }

  resolve(id: number): RegisteredElement | undefined {
    const registered = this.#elements.get(id);
    if (registered && !registered.element.isConnected) {
      this.#elements.delete(id);
      return undefined;
    }
    return registered;
  }

  isSensitiveNow(element: Element): boolean {
    return isSensitiveField(element, accessibleName(element));
  }

  isVisibleNow(element: Element): boolean {
    return (this.#options.isVisible ?? defaultVisibility)(element);
  }

  build(): Snapshot {
    const started = performance.now();
    try {
      return this.#build();
    } finally {
      recordEvaluationTiming("snapshot_build", started);
    }
  }

  #build(): Snapshot {
    for (const [id, registered] of this.#elements)
      if (!registered.element.isConnected) this.#elements.delete(id);
    const elements = [...this.#document.querySelectorAll("*")]
      .map((element) => this.#describe(element))
      .filter((element): element is SnapshotElement => element !== undefined);
    const snapshot = this.#snapshot(elements, false);
    if (
      new TextEncoder().encode(JSON.stringify(snapshot)).length <=
      SNAPSHOT_BUDGET_BYTES
    ) {
      return snapshot;
    }

    const visible = elements.filter((element) => element.visible);
    const withoutLowValue = visible.filter(
      (element) => element.role !== "heading" && element.role !== "option",
    );
    const candidates = [visible, withoutLowValue];
    for (const candidate of candidates) {
      const truncated = this.#snapshot(candidate, true);
      if (
        new TextEncoder().encode(JSON.stringify(truncated)).length <=
        SNAPSHOT_BUDGET_BYTES
      ) {
        return truncated;
      }
    }
    return this.#snapshot(withoutLowValue.slice(0, 50), true);
  }

  #snapshot(elements: SnapshotElement[], truncated: boolean): Snapshot {
    const view = this.#document.defaultView;
    return {
      v: 1,
      url: this.#options.url?.() ?? view?.location.href ?? "",
      title: this.#document.title,
      lang: this.#document.documentElement.lang || "en",
      viewport: this.#options.viewport ?? {
        w: view?.innerWidth ?? 0,
        h: view?.innerHeight ?? 0,
        scrollY: Math.round(view?.scrollY ?? 0),
      },
      truncated,
      elements,
    };
  }

  #describe(element: Element): SnapshotElement | undefined {
    const role = elementRole(element);
    if (role === undefined || !INTERACTIVE_ROLES.has(role)) return undefined;
    const name = accessibleName(element);
    const visible = this.isVisibleNow(element);
    const sensitive = isSensitiveField(element, name);
    const id = this.#idFor(element);
    this.#elements.set(id, { element, sensitive });
    const base: SnapshotElement = { id, role, name, visible };
    if (sensitive) return { ...base, name: "Sensitive field", sensitive: true };

    const region = nearestRegion(element);
    const group = nearestGroup(element);
    return {
      ...base,
      ...optionalState(element, role),
      ...(region === undefined ? {} : { region }),
      ...(group === undefined || group === "" ? {} : { group }),
    };
  }

  #idFor(element: Element): number {
    const existing = this.#ids.get(element);
    if (existing !== undefined) return existing;
    const id = this.#nextId++;
    this.#ids.set(element, id);
    return id;
  }
}
import { documentIsBusy } from "./observation.js";
