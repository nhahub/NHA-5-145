/* global window, document, URL, URLSearchParams, fetch, DOMParser, FormData, Event, CustomEvent, setTimeout */
(() => {
  const selected = new URL(window.location.href).searchParams.get("spa");
  if (selected === "off") window.sessionStorage.removeItem("storefront.spa");
  else if (selected === "url" || selected === "component")
    window.sessionStorage.setItem("storefront.spa", selected);
  const mode = window.sessionStorage.getItem("storefront.spa");
  if (!mode || !window.navigation) return;
  document.documentElement.dataset.spaMode = mode;
  const initial = new URL(window.location.href);
  initial.searchParams.delete("spa");
  window.history.replaceState(null, "", initial);
  const componentFilters = new Map();
  let committingHistory = false;
  let generation = 0;
  const isCategory = (url) =>
    /^\/c\/(shoes|clothing|bags|electronics)$/.test(url.pathname);
  const eligible = (url) =>
    url.origin === window.location.origin &&
    (isCategory(url) ||
      ["/cart", "/account", "/account/orders"].includes(url.pathname));

  function commitHistory(url, replace = false) {
    committingHistory = true;
    try {
      window.history[replace ? "replaceState" : "pushState"](null, "", url);
    } finally {
      committingHistory = false;
    }
  }

  function mountControlledFilters() {
    const form = document.querySelector('main form[method="get"]');
    if (!form) return;
    // Draft filter state commits through input/change events, independently of the URL.
    const draft = new Map();
    const fields = [...form.querySelectorAll("input, select")];
    const remember = (field) =>
      draft.set(field, { value: field.value, checked: field.checked });
    fields.forEach(remember);
    const commit = (event) => {
      if (!draft.has(event.target)) return;
      fields.forEach(remember);
      window.requestAnimationFrame(() => {
        for (const [field, state] of draft) {
          if (!field.isConnected) continue;
          field.value = state.value;
          if ("checked" in field) field.checked = state.checked;
        }
      });
    };
    form.addEventListener("input", commit);
    form.addEventListener("change", commit);
  }

  async function render(destination, { signal, submitted = false } = {}) {
    const ticket = ++generation;
    const requestUrl = new URL(destination);
    if (mode === "component" && isCategory(requestUrl)) {
      if (submitted)
        componentFilters.set(requestUrl.pathname, requestUrl.search);
      requestUrl.search = componentFilters.get(requestUrl.pathname) || "";
    }
    const main = document.querySelector("main");
    main.setAttribute("aria-busy", "true");
    main.inert = true;
    main.innerHTML = '<p role="status">جارٍ تحميل الصفحة…</p>';
    try {
      const response = await fetch(requestUrl, { cache: "no-store", signal });
      // Authentication and non-SPA redirects keep their normal document lifecycle.
      if (response.redirected) {
        if (new URL(response.url).origin !== window.location.origin)
          throw new Error("Untrusted redirect");
        window.location.assign(response.url);
        return;
      }
      if (!response.ok) throw new Error("Page unavailable");
      const parsed = new DOMParser().parseFromString(
        await response.text(),
        "text/html",
      );
      const content = parsed.querySelector("main");
      if (!content) throw new Error("Page unavailable");
      // A deliberate loading interval exercises settled observation rather than URL-only success.
      await new Promise((resolve) => setTimeout(resolve, 350));
      if (ticket !== generation || signal?.aborted) return;
      for (const name of ["copilot-csrf", "copilot-context"]) {
        const incoming = parsed.querySelector('meta[name="' + name + '"]');
        const current = document.querySelector('meta[name="' + name + '"]');
        if (!incoming || !current)
          throw new Error("Shopper context unavailable");
        current.content = incoming.content;
      }
      main.replaceChildren(...content.childNodes);
      document.title = parsed.title;
      const pending = [];
      document.dispatchEvent(
        new CustomEvent("storefront:render", {
          detail: { waitUntil: (promise) => pending.push(promise) },
        }),
      );
      await Promise.all(pending);
      mountControlledFilters();
      // Finish the intercepted navigation before canonicalising its history entry.
      // Replacing history inside the handler would abort navigation.finished.
      if (mode === "component" && isCategory(requestUrl))
        window.setTimeout(() => {
          if (ticket === generation) commitHistory(requestUrl.pathname, true);
        }, 0);
    } catch (error) {
      if (ticket !== generation || signal?.aborted) return;
      main.innerHTML =
        '<p role="alert">تعذر تحميل الصفحة. حدّث الصفحة للمحاولة مجددًا.</p>';
      throw error;
    } finally {
      if (ticket === generation) {
        main.inert = false;
        main.removeAttribute("aria-busy");
        document.dispatchEvent(new Event("change"));
      }
    }
  }

  window.navigation.addEventListener("navigate", (event) => {
    const destination = new URL(event.destination.url);
    if (
      committingHistory ||
      !event.canIntercept ||
      event.hashChange ||
      event.navigationType === "reload" ||
      event.formData ||
      !eligible(destination)
    )
      return;
    if (document.documentElement.hasAttribute("data-cart-pending")) {
      if (event.cancelable) event.preventDefault();
      return;
    }
    if (
      mode === "component" &&
      isCategory(destination) &&
      event.navigationType !== "traverse"
    )
      componentFilters.delete(destination.pathname);
    event.intercept({
      handler: () => render(destination, { signal: event.signal }),
    });
  });
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (form.method !== "get") return;
    const destination = new URL(form.action);
    if (!eligible(destination) || !isCategory(destination)) return;
    event.preventDefault();
    if (document.documentElement.hasAttribute("data-cart-pending")) return;
    destination.search = new URLSearchParams(
      [...new FormData(form)].filter(([, value]) => value !== ""),
    ).toString();
    commitHistory(mode === "component" ? destination.pathname : destination);
    void render(destination, { submitted: true });
  });
  mountControlledFilters();
})();
