/** Observe client-side page transitions without depending on a particular router. */
export function observeDocument(
  document: Document,
  changed: (route: boolean, committed?: boolean) => void,
): () => void {
  const view = document.defaultView;
  if (!view) return () => undefined;
  const contentChanged = () => changed(false);
  const committedChange = () => changed(false, true);
  const routeChanged = () => changed(true);
  const observer = new view.MutationObserver(contentChanged);
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: [
      "aria-busy",
      "hidden",
      "disabled",
      "value",
      "checked",
      "aria-expanded",
      "aria-label",
      "aria-labelledby",
      "aria-checked",
      "aria-selected",
      "href",
      "role",
      "inert",
      "data-cart-pending",
    ],
  });
  document.addEventListener("change", committedChange);
  document.addEventListener("input", contentChanged);
  view.addEventListener("popstate", routeChanged);
  view.addEventListener("hashchange", routeChanged);
  const navigation = (view as Window & { navigation?: EventTarget }).navigation;
  navigation?.addEventListener("navigatesuccess", routeChanged);
  const push = view.history.pushState;
  const replace = view.history.replaceState;
  const wrap = (method: typeof push): typeof push =>
    function (...args) {
      method.apply(view.history, args);
      routeChanged();
    };
  const wrappedPush = wrap(push);
  const wrappedReplace = wrap(replace);
  view.history.pushState = wrappedPush;
  view.history.replaceState = wrappedReplace;
  return () => {
    observer.disconnect();
    document.removeEventListener("change", committedChange);
    document.removeEventListener("input", contentChanged);
    view.removeEventListener("popstate", routeChanged);
    view.removeEventListener("hashchange", routeChanged);
    navigation?.removeEventListener("navigatesuccess", routeChanged);
    if (view.history.pushState === wrappedPush) view.history.pushState = push;
    if (view.history.replaceState === wrappedReplace)
      view.history.replaceState = replace;
  };
}

export function documentIsBusy(document: Document): boolean {
  return (
    document.querySelector('[aria-busy="true"], [data-cart-pending]') !== null
  );
}

export async function settleDocument(document: Document): Promise<void> {
  const view = document.defaultView;
  if (!view) return;
  // An initial delay lets controlled inputs commit and routers mount content.
  await new Promise<void>((resolve) => view.setTimeout(resolve, 300));
  const start = Date.now();
  while (documentIsBusy(document) && Date.now() - start < 10000)
    await new Promise<void>((resolve) => view.setTimeout(resolve, 25));
}
