/* global document, window, IntersectionObserver, setTimeout, Event */
let disposeInteractions = () => {};
function mountInteractions() {
  disposeInteractions();
  const cleanup = [];
  const filterDrawer = document.getElementById("filter-drawer");
  if (filterDrawer) {
    const media = window.matchMedia("(max-width: 600px)");
    const syncDrawer = () => {
      filterDrawer.open = !media.matches;
      filterDrawer.dataset.mobileReady = "true";
    };
    syncDrawer();
    media.addEventListener("change", syncDrawer);
    cleanup.push(() => media.removeEventListener("change", syncDrawer));
  }
  const size = document.getElementById("product-size");
  const swatches = [...document.querySelectorAll("[data-size-swatch]")];
  const syncSwatches = () => {
    for (const swatch of swatches)
      swatch.setAttribute(
        "aria-pressed",
        String(swatch.dataset.sizeSwatch === size?.value),
      );
  };
  for (const swatch of swatches)
    swatch.addEventListener("click", () => {
      size.value = swatch.dataset.sizeSwatch;
      size.dispatchEvent(new Event("change", { bubbles: true }));
      size.focus();
    });
  size?.addEventListener("change", syncSwatches);
  syncSwatches();

  const sortTrigger = document.getElementById("sort-trigger");
  const sortOptions = document.getElementById("sort-options");
  const nativeSort = document.getElementById("sort");
  const closeSort = () => {
    if (!sortOptions) return;
    sortOptions.hidden = true;
    sortTrigger.setAttribute("aria-expanded", "false");
  };
  sortTrigger?.addEventListener("click", () => {
    sortOptions.hidden = !sortOptions.hidden;
    sortTrigger.setAttribute("aria-expanded", String(!sortOptions.hidden));
    if (!sortOptions.hidden)
      sortOptions.querySelector("[role=option]")?.focus();
  });
  sortOptions?.addEventListener("click", (event) => {
    const option = event.target.closest("[data-sort-value]");
    if (!option) return;
    nativeSort.value = option.dataset.sortValue;
    nativeSort.dispatchEvent(new Event("change", { bubbles: true }));
    sortTrigger.textContent = option.textContent;
    for (const sibling of sortOptions.querySelectorAll("[role=option]"))
      sibling.setAttribute("aria-selected", String(sibling === option));
    closeSort();
    sortTrigger.focus();
  });
  sortOptions?.addEventListener("keydown", (event) => {
    const options = [...sortOptions.querySelectorAll("[role=option]")];
    const index = options.indexOf(document.activeElement);
    if (event.key === "Escape") {
      closeSort();
      sortTrigger.focus();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      options[
        (index + (event.key === "ArrowDown" ? 1 : options.length - 1)) %
          options.length
      ]?.focus();
    }
  });

  const template = document.getElementById("remaining-products");
  const loadMore = document.getElementById("load-more-products");
  const results = document.getElementById("product-results");
  const loading = document.getElementById("loading-products");
  let loadingNow = false;
  function revealNext() {
    if (!template?.content.children.length || loadingNow) return;
    loadingNow = true;
    loadMore.disabled = true;
    results.setAttribute("aria-busy", "true");
    loading.hidden = false;
    setTimeout(() => {
      for (const item of [...template.content.children].slice(0, 6))
        results.insertBefore(item, template);
      const more = template.content.children.length > 0;
      loadMore.hidden = !more;
      loadMore.disabled = false;
      loading.hidden = true;
      results.removeAttribute("aria-busy");
      loadingNow = false;
      document.dispatchEvent(new Event("change"));
    }, 350);
  }
  loadMore?.addEventListener("click", revealNext);
  if (loadMore && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) revealNext();
    });
    observer.observe(loadMore);
    cleanup.push(() => observer.disconnect());
  }
  disposeInteractions = () => cleanup.forEach((dispose) => dispose());
}
mountInteractions();
document.addEventListener("storefront:render", mountInteractions);
