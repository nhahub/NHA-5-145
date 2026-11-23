import { SnapshotBuilder } from "./snapshot.js";
import type { Action, ActionResult, ActionResultStatus } from "./types.js";
import { documentIsBusy } from "./observation.js";

export interface ActionEnvironment {
  builder: SnapshotBuilder;
  currentUrl: () => string;
  storefrontOrigin: string;
  navigate: (url: URL) => Promise<void>;
  settle: () => Promise<void>;
  armGuardedNavigation?: (
    action: Extract<Action, { type: "guarded_click" }>,
  ) => void;
}

function result(
  action: Action,
  status: ActionResultStatus,
  builder: SnapshotBuilder,
): ActionResult {
  return {
    v: 1,
    task_id: action.task_id,
    action_id: action.action_id,
    sequence_number: action.sequence_number,
    status,
    snapshot: builder.build(),
  };
}

function scrollIntoView(element: Element): void {
  if (
    "scrollIntoView" in element &&
    typeof element.scrollIntoView === "function"
  ) {
    element.scrollIntoView({ block: "center" });
  }
}

function spotlight(element: Element, message: string): void {
  const view = element.ownerDocument.defaultView;
  const reduceMotion =
    view?.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

  element.setAttribute("data-copilot-spotlight", message);
  if (view !== null && element instanceof view.HTMLElement) {
    element.style.outline = "3px solid #c2410c";
    element.style.outlineOffset = "4px";
    element.style.boxShadow = "0 0 0 6px rgb(234 88 12 / 25%)";
    element.style.borderRadius ||= "4px";
  }

  if (
    "scrollIntoView" in element &&
    typeof element.scrollIntoView === "function"
  ) {
    element.scrollIntoView({
      behavior: reduceMotion ? "instant" : "smooth",
      block: "center",
      inline: "center",
    });
  }
}

function setElementValue(element: Element, value: string): boolean {
  const view = element.ownerDocument.defaultView;
  if (view === null) return false;
  if (element instanceof view.HTMLInputElement) {
    const setter = Object.getOwnPropertyDescriptor(
      view.HTMLInputElement.prototype,
      "value",
    )?.set;
    setter?.call(element, value);
  } else if (element instanceof view.HTMLTextAreaElement) {
    const setter = Object.getOwnPropertyDescriptor(
      view.HTMLTextAreaElement.prototype,
      "value",
    )?.set;
    setter?.call(element, value);
  } else {
    return false;
  }
  element.dispatchEvent(new view.Event("input", { bubbles: true }));
  element.dispatchEvent(new view.Event("change", { bubbles: true }));
  return true;
}

function destinationIsTrusted(
  destination: string,
  currentUrl: string,
  storefrontOrigin: string,
): boolean {
  try {
    return (
      new URL(currentUrl).origin === storefrontOrigin &&
      new URL(destination, currentUrl).origin === storefrontOrigin
    );
  } catch {
    return false;
  }
}

function interactionDestination(
  element: Element,
  action: Action,
): string | null {
  if (action.type === "click" || action.type === "guarded_click") {
    const link = element.closest("a[href], area[href]");
    if (link !== null)
      return new URL(link.getAttribute("href")!, link.baseURI).href;
  }
  if (
    action.type === "click" ||
    action.type === "guarded_click" ||
    (action.type === "type" && action.submit)
  ) {
    return formInteraction(element, action)?.destination ?? null;
  }
  return null;
}

function formInteraction(actionTarget: Element, action: Action) {
  // A click on a described descendant activates its enclosing native button.
  const element =
    action.type === "click" || action.type === "guarded_click"
      ? (actionTarget.closest("button, input") ?? actionTarget)
      : actionTarget;
  const view = element.ownerDocument.defaultView;
  if (view === null) return null;
  const control =
    element instanceof view.HTMLButtonElement ||
    element instanceof view.HTMLInputElement ||
    element instanceof view.HTMLTextAreaElement ||
    element instanceof view.HTMLSelectElement;
  const form = control ? element.form : element.closest("form");
  if (form === null) return null;
  const isSubmitter =
    (action.type === "click" || action.type === "guarded_click") &&
    ((element instanceof view.HTMLButtonElement && element.type === "submit") ||
      (element instanceof view.HTMLInputElement &&
        ["submit", "image"].includes(element.type)));
  const override = isSubmitter ? element.getAttribute("formaction") : null;
  return {
    form,
    destination:
      override === null
        ? form.action
        : override === ""
          ? element.ownerDocument.URL
          : new URL(override, element.baseURI).href,
    method: (
      (isSubmitter ? element.getAttribute("formmethod") : null) ?? form.method
    ).toLowerCase(),
  };
}

function matchingGuardedForm(
  action: Extract<Action, { type: "guarded_click" }>,
  element: Element,
  builder: SnapshotBuilder,
): HTMLFormElement | null {
  const view = element.ownerDocument.defaultView;
  const interaction = formInteraction(element, action);
  if (view === null || interaction === null) return null;
  const { form } = interaction;
  const current = builder
    .build()
    .elements.find((item) => item.id === action.id);
  const route =
    action.mutation_kind === "clear_cart" ? "/cart/clear" : "/checkout/submit";
  const expectedEffect =
    action.mutation_kind === "clear_cart"
      ? "Remove every item from the current cart"
      : "Submit one fictional order for the current cart";
  if (
    current?.role !== "button" ||
    !current.visible ||
    current.disabled ||
    interaction.method !== "post" ||
    current.form_action !== route ||
    current.mutation_state !== `cart:${action.cart_revision}` ||
    action.state_signature !== current.mutation_state ||
    action.target_signature !== `button|${current.name}|POST ${route}` ||
    action.effect !== expectedEffect ||
    !/^confirmation-[0-9a-f]{32}$/.test(action.confirmation_id) ||
    !form.checkValidity()
  )
    return null;
  const revision = form.querySelector<HTMLInputElement>(
    'input[name="cart_revision"]',
  );
  const token = form.querySelector<HTMLInputElement>(
    'input[name="copilot_confirmation"]',
  );
  if (
    revision?.value !== String(action.cart_revision) ||
    token === null ||
    !(token instanceof view.HTMLInputElement)
  )
    return null;
  token.value = action.confirmation_id;
  return form;
}

function isGuardedFormInteraction(element: Element, action: Action): boolean {
  if (action.type !== "click" && !(action.type === "type" && action.submit))
    return false;
  const interaction = formInteraction(element, action);
  if (interaction === null || interaction.method !== "post") return false;
  // Express matches Controlled Storefront routes case-insensitively and
  // accepts a trailing slash; those spellings must have the same policy.
  const destination = new URL(interaction.destination).pathname
    .replace(/\/+$/, "")
    .toLowerCase();
  return destination === "/cart/clear" || destination === "/checkout/submit";
}

export async function executeAction(
  action: Action,
  environment: ActionEnvironment,
): Promise<ActionResult> {
  if (action.type === "navigate") {
    const current = new URL(environment.currentUrl());
    const destination = new URL(action.url, current);
    const trustedOrigin = environment.storefrontOrigin;
    if (
      current.origin !== trustedOrigin ||
      destination.origin !== trustedOrigin
    ) {
      return result(action, "blocked", environment.builder);
    }
    try {
      await environment.navigate(destination);
    } catch {
      return result(action, "blocked", environment.builder);
    }
    await environment.settle();
    return result(
      action,
      environment.builder.isBusy() ? "blocked" : "navigated",
      environment.builder,
    );
  }

  if (action.type === "ask_shopper" || action.type === "done") {
    return result(action, "ok", environment.builder);
  }

  const registered = environment.builder.resolve(action.id);
  if (registered === undefined)
    return result(action, "not_found", environment.builder);
  const { element, sensitive } = registered;
  if (
    !environment.builder.isVisibleNow(element) ||
    element.closest('[inert], [aria-disabled="true"], fieldset[disabled]') ||
    element.matches(":disabled")
  )
    return result(action, "blocked", environment.builder);
  let cartForm: HTMLFormElement | undefined;
  let interactionUrl: string | null;
  try {
    interactionUrl = interactionDestination(element, action);
    cartForm = formInteraction(element, action)?.form;
  } catch {
    return result(action, "blocked", environment.builder);
  }
  if (
    interactionUrl !== null &&
    !destinationIsTrusted(
      interactionUrl,
      environment.currentUrl(),
      environment.storefrontOrigin,
    )
  ) {
    return result(action, "blocked", environment.builder);
  }
  if (isGuardedFormInteraction(element, action)) {
    return result(action, "blocked", environment.builder);
  }
  const isCartSubmission =
    (action.type === "click" || (action.type === "type" && action.submit)) &&
    cartForm?.hasAttribute("data-cart-edit");
  if (isCartSubmission) {
    if (
      !cartForm?.checkValidity() ||
      element.ownerDocument.documentElement.hasAttribute("data-cart-pending")
    )
      return result(action, "blocked", environment.builder);
    cartForm.removeAttribute("data-cart-result");
  }
  if (
    (action.type === "type" || action.type === "select") &&
    (sensitive || environment.builder.isSensitiveNow(element))
  ) {
    return result(action, "blocked", environment.builder);
  }

  if (
    (action.type === "click" || action.type === "guarded_click") &&
    element instanceof element.ownerDocument.defaultView!.HTMLElement &&
    element.matches(":disabled, [aria-disabled='true']")
  ) {
    return result(action, "blocked", environment.builder);
  }

  if (action.type === "guarded_click") {
    if (matchingGuardedForm(action, element, environment.builder) === null)
      return result(action, "blocked", environment.builder);
    environment.armGuardedNavigation?.(action);
  }

  if (action.type !== "spotlight") scrollIntoView(element);
  let status: ActionResultStatus = "ok";
  let expectedValue: string | undefined;
  if (action.type === "click" || action.type === "guarded_click") {
    if (element instanceof element.ownerDocument.defaultView!.HTMLElement)
      element.click();
    else status = "not_found";
  } else if (action.type === "type") {
    if (!setElementValue(element, action.text)) status = "not_found";
    else if (action.submit) {
      await environment.settle();
      if (
        !element.isConnected ||
        !("value" in element) ||
        element.value !== action.text ||
        documentIsBusy(element.ownerDocument)
      )
        return result(action, "blocked", environment.builder);
      const form = formInteraction(element, action)?.form;
      form?.requestSubmit();
    } else expectedValue = action.text;
  } else if (action.type === "select") {
    const view = element.ownerDocument.defaultView;
    if (view !== null && element instanceof view.HTMLSelectElement) {
      const option = [...element.options].find(
        (candidate) =>
          !candidate.disabled &&
          (candidate.value === action.option ||
            candidate.text === action.option),
      );
      if (option === undefined) status = "not_found";
      else {
        expectedValue = option.value;
        Object.getOwnPropertyDescriptor(
          view.HTMLSelectElement.prototype,
          "value",
        )?.set?.call(element, option.value);
        element.dispatchEvent(new view.Event("input", { bubbles: true }));
        element.dispatchEvent(new view.Event("change", { bubbles: true }));
      }
    } else status = "not_found";
  } else if (action.type === "spotlight") {
    spotlight(element, action.message);
  }

  await environment.settle();
  if (
    documentIsBusy(element.ownerDocument) ||
    (expectedValue !== undefined &&
      (!element.isConnected ||
        !("value" in element) ||
        element.value !== expectedValue))
  )
    status = "blocked";
  if (isCartSubmission) {
    const start = Date.now();
    while (
      element.ownerDocument.documentElement.hasAttribute("data-cart-pending") &&
      Date.now() - start < 10000
    ) {
      await new Promise((resolve) => setTimeout(resolve, 25));
    }
    if (cartForm?.getAttribute("data-cart-result") !== "confirmed")
      status = "blocked";
  }
  return result(action, status, environment.builder);
}
