/* global document, fetch, FormData, crypto, performance, setTimeout, clearTimeout, AbortSignal, Event, CSS */
(() => {
  let state = null;
  let busy = false;
  let timer;
  let deadline = 0;
  const ar = () => document.documentElement.lang !== "en";
  const feedback = document.getElementById("cart-feedback");
  const undoForm = document.getElementById("undo-form");
  const badge = document.querySelector('header a[href="/cart"]');
  const miniCartCount = document.getElementById("mini-cart-count");
  const miniCartSummary = document.getElementById("mini-cart-summary");
  const messages = {
    add: ["تمت الإضافة إلى السلة", "Added to cart"],
    quantity: ["تم تحديث الكمية", "Quantity updated"],
    remove: ["تم حذف المنتج من السلة", "Item removed from cart"],
    undo: ["تم التراجع عن تعديل السلة", "Cart change undone"],
  };
  function toast(undo) {
    clearTimeout(timer);
    undoForm.hidden = !undo;
    if (!undo) return;
    deadline = performance.now() + undo.remaining_ms;
    document.getElementById("undo-description").textContent = ar()
      ? undo.description
      : undo.description_en;
    undoForm.querySelector("button").textContent = ar() ? "تراجع" : "Undo";
    const tick = () => {
      const left = Math.max(
        0,
        Math.ceil((deadline - performance.now()) / 1000),
      );
      document.getElementById("undo-timer").textContent =
        `${left} ${ar() ? "ث" : "s"}`;
      if (!left) undoForm.hidden = true;
      else timer = setTimeout(tick, 100);
    };
    tick();
  }
  let focusTarget;
  function restoreFocus() {
    if (!focusTarget) return;
    const target = document.querySelector(focusTarget);
    if (target) target.focus();
    else if (!undoForm.hidden) undoForm.querySelector("button").focus();
  }
  function render(next, showUndo = true) {
    if (
      next.shopper_context !==
      document.querySelector('meta[name="copilot-context"]')?.content
    ) {
      document.documentElement.dataset.shopperInvalid = "true";
      document.dispatchEvent(new Event("shopper:reset"));
      throw new Error("Shopper context changed; reload before continuing");
    }
    state = next;
    badge.textContent = `السلة (${next.count})`;
    if (miniCartCount) miniCartCount.textContent = String(next.count);
    if (miniCartSummary)
      miniCartSummary.textContent = next.lines.length
        ? `السلة فيها ${next.lines.length} منتج، ${next.count} قطعة`
        : "السلة فارغة";
    const contents = document.getElementById("cart-contents");
    if (contents) {
      const incoming = document.createElement("div");
      incoming.innerHTML = next.html;
      // Cart fragments replace native guarded forms too. Preserve browser authority.
      for (const form of incoming.querySelectorAll('form[method="post"]')) {
        const csrf = document.createElement("input");
        csrf.type = "hidden";
        csrf.name = "copilot_csrf";
        csrf.dataset.sensitive = "true";
        csrf.value = document.querySelector(
          'meta[name="copilot-csrf"]',
        ).content;
        form.prepend(csrf);
      }
      // Initial state hydration must not detach controls already observed by
      // the Bridge when the server-rendered cart is unchanged.
      if (contents.innerHTML !== incoming.innerHTML)
        contents.replaceChildren(...incoming.childNodes);
    }
    document.documentElement.dataset.cartRevision = String(next.revision);
    toast(showUndo ? next.undo : null);
    restoreFocus();
    document.dispatchEvent(new Event("change"));
  }
  async function refresh(showUndo = true) {
    const response = await fetch("/cart/state", { cache: "no-store" });
    if (!response.ok) throw new Error("Cart unavailable");
    render(await response.json(), showUndo);
  }
  const ready = refresh().catch(() => {
    feedback.textContent = ar()
      ? "تعذر تحميل السلة. أعد تحميل الصفحة."
      : "Cart unavailable. Reload the page.";
  });
  document.addEventListener("storefront:render", (event) => {
    event.detail.waitUntil(refresh());
  });
  let confirmingClear = false;
  document.addEventListener("click", async (event) => {
    const clearDialog = document.getElementById("manual-clear-dialog");
    if (!event.isTrusted || !clearDialog) return;
    const trigger = event.target.closest('[data-testid="empty-cart"]');
    if (trigger) {
      event.preventDefault();
      if (busy || !state?.lines.length) return;
      const form = document.getElementById("manual-clear-form");
      form.elements.cart_revision.value = String(state.revision);
      form.elements.copilot_confirmation.value = "";
      document.getElementById("confirm-manual-clear").dataset.cartRevision =
        String(state.revision);
      document.getElementById("manual-clear-summary").textContent =
        `عدد المنتجات: ${state.count}`;
      clearDialog.showModal();
    }
    if (event.target.closest("#cancel-manual-clear")) {
      event.preventDefault();
      if (!confirmingClear) clearDialog.close();
    }
    if (event.target.closest("#confirm-manual-clear")) {
      event.preventDefault();
      if (confirmingClear || busy) return;
      confirmingClear = true;
      const form = document.getElementById("manual-clear-form");
      const button = document.getElementById("confirm-manual-clear");
      button.disabled = true;
      try {
        const response = await fetch("/__copilot/manual-confirmation", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-csrf-token": document.querySelector('meta[name="copilot-csrf"]')
              ?.content,
          },
          body: JSON.stringify({
            kind: "clear_cart",
            cart_revision: Number(form.elements.cart_revision.value),
          }),
          signal: AbortSignal.timeout(8000),
        });
        if (!response.ok) throw new Error("Stale cart confirmation");
        if (!clearDialog.open) return;
        form.elements.copilot_confirmation.value = (
          await response.json()
        ).token;
        form.requestSubmit();
      } catch {
        document.getElementById("manual-clear-summary").textContent =
          "تغيّرت السلة أو تعذر تأكيد الطلب. أغلق الرسالة وأعد تحميل السلة قبل المحاولة مجددًا.";
      } finally {
        confirmingClear = false;
        button.disabled = false;
      }
    }
  });
  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!form.matches("form[data-cart-edit]")) return;
    event.preventDefault();
    if (busy) return;
    busy = true;
    document.documentElement.dataset.cartPending = "true";
    const kind = form.dataset.cartEdit;
    feedback.setAttribute("role", "status");
    form.dataset.cartResult = "pending";
    let beforeHtml;
    let beforeBadge;
    const contents = document.getElementById("cart-contents");
    const focused = document.activeElement;
    focusTarget = undefined;
    if (contents?.contains(focused)) {
      const row = focused.closest("[data-cart-line]");
      const edit = focused.closest("[data-cart-edit]");
      if (row && edit)
        focusTarget = `[data-cart-line="${CSS.escape(row.dataset.cartLine)}"] [data-cart-edit="${edit.dataset.cartEdit}"] ${focused.tagName === "INPUT" ? 'input[name="quantity"]' : "button"}`;
    }
    try {
      await ready;
      if (!state) throw new Error("Cart unavailable");
      const data = Object.fromEntries(new FormData(form));
      if ("quantity" in data) data.quantity = Number(data.quantity);
      Object.assign(data, {
        revision: state.revision,
        operation_id: crypto.randomUUID(),
      });
      if (kind === "undo") data.undo_id = state.undo?.id;
      beforeHtml = contents?.innerHTML;
      beforeBadge = badge.textContent;
      let count = state.count;
      if (kind === "add") count += data.quantity;
      else if (kind === "quantity" || kind === "remove") {
        const line = state.lines.find(
          (line) =>
            line.product_id === data.product_id &&
            (line.size ?? "") === data.size &&
            (line.color ?? "") === data.color,
        );
        if (line)
          count +=
            kind === "remove" ? -line.quantity : data.quantity - line.quantity;
        if (kind === "remove") form.closest("[data-cart-line]").hidden = true;
      }
      badge.textContent = `السلة (${count})`;
      if (contents && (kind === "quantity" || kind === "remove")) {
        const rows = [...contents.querySelectorAll("[data-cart-line]")].filter(
          (row) => !row.hidden,
        );
        contents.querySelector('[role="status"]').textContent = rows.length
          ? `السلة فيها ${rows.length} منتج`
          : "السلة فارغة";
        const total = rows.reduce((sum, row) => {
          const [whole, fraction = ""] = row.dataset.unitPrice.split(".");
          return (
            sum +
            (BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"))) *
              BigInt(row.querySelector('input[name="quantity"]').value)
          );
        }, 0n);
        contents.querySelector(".cart-total strong").textContent =
          `${total / 100n}.${String(total % 100n).padStart(2, "0")} EGP`;
      }
      feedback.textContent = ar() ? "جارٍ تحديث السلة…" : "Updating cart…";
      document.querySelectorAll("[data-cart-edit] button").forEach((button) => {
        button.disabled = true;
      });
      const response = await fetch(form.action, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-csrf-token": document.querySelector('meta[name="copilot-csrf"]')
            ?.content,
        },
        body: JSON.stringify(data),
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) throw new Error("Cart edit rejected");
      render(await response.json());
      form.dataset.cartResult = "confirmed";
      feedback.textContent = messages[kind][ar() ? 0 : 1];
      feedback.dataset.cartResult = "confirmed";
    } catch {
      if (contents && beforeHtml !== undefined) contents.innerHTML = beforeHtml;
      if (beforeBadge !== undefined) badge.textContent = beforeBadge;
      toast(null);
      form.dataset.cartResult = "failed";
      feedback.dataset.cartResult = "failed";
      feedback.textContent = ar()
        ? "تعذر تأكيد تعديل السلة. لم نكرر العملية؛ راجع السلة قبل المحاولة مجددًا."
        : "Cart change was not confirmed. Check the cart before trying again; it was not repeated.";
      try {
        await refresh(false);
      } catch {
        state = null;
      }
    } finally {
      busy = false;
      delete document.documentElement.dataset.cartPending;
      document.querySelectorAll("[data-cart-edit] button").forEach((button) => {
        button.disabled = false;
      });
      restoreFocus();
      focusTarget = undefined;
    }
  });
})();
