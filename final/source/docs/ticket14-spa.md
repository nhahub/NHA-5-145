# Ticket 14: client-side navigation

The approved local ticket is `.scratch/shopping-copilot-local-mvp/issues/14-preserve-behaviour-across-spa-navigation.md`. This work preserves the existing Action and Snapshot contracts and model-owned interpretation.

## Design and verification

- Add opt-in `?spa=url` and `?spa=component` storefront variants, remembered per browser tab. Category, cart and account routes keep their existing destinations. Default server-rendered browsing remains available with `?spa=off`.
- The controlled storefront uses the browser Navigation API to intercept eligible same-origin GET navigation and render a settled main region. Component mode deliberately ignores URL filter shortcuts; submitting visible filters applies component state. A visible current-results link represents the filters actually rendered, independently of draft inputs or address-bar parameters.
- The Bridge observes history and DOM changes, waits for loading/optimistic state, verifies controlled input values after settling, and reports same-document navigation results without waiting for a new document. Existing action identity, sensitive-field and origin checks remain enforced.
- The Agent uses observed applied-result state for discovery completion and visible-control fallback. Event-stream reconnect honors `Last-Event-ID`; the Panel ignores already delivered event cursors.
- Test public Bridge, Agent HTTP and actual browser boundaries. Compare action counts for URL versus component state, verify back/forward and stale targets, and exercise cart Undo, guarded confirmation, refresh and duplicate delivery. Use explicit scripted decisions for deterministic execution tests, with no paid model calls.

The Navigation API integration follows the [Chrome platform documentation](https://developer.chrome.com/docs/web-platform/navigation-api). It is a controlled Chromium stress variant, not independent-storefront generalisation.

## Manual entry points

Open `http://localhost:4100/?spa=url` for URL-backed filters, `http://localhost:4100/?spa=component` for component-only filters, or `http://localhost:4100/?spa=off` for ordinary document navigation. The mode is tab-local and remains active through refresh; it does not change the Agent provider or budget.

## Evidence and review

The browser comparison reaches the same three running-shoe results under 2,000 EGP in **one Action with URL state** and **three Actions with component state**. Both retain the same document. Additional cases cover history traversal, delayed DOM observations, quantity changes with exact Undo after refresh, expired Confirmation followed by a newly bound Confirmation, reconnect with duplicate delivery, stale targets, blocked off-origin navigation, and failed page loads.

The reconnect browser harness deliberately closes streams and replays events; it verifies one cart write and one completion message. It does not claim to inspect Chromium's automatic `Last-Event-ID` header. The HTTP regression independently verifies server cursor handling, and the Panel transport regression verifies duplicate suppression.

The first full run exposed delayed committed selections reaching the Agent with their previous values. Committed `change` events now publish immediately when the document is ready, while optimistic/loading state waits and a subsequent settled observation captures later component changes. A Bridge regression verifies both sides of that boundary. An older mobile fixture also expected copy replaced by commit `d7f6d12`; it now verifies the Stop handback, zero Actions, and unchanged cart. Review caught a failed SPA fetch resolving as successful navigation; it now rejects the navigation and returns a blocked Action Result.

Standards and Spec were reviewed locally against `d7f6d12` and the approved ticket. No independent sub-agent review was run in this side conversation. These tests establish execution behavior on the controlled storefront; they are not new live-model language evidence. No paid provider calls were made.

Final checks: **398 Python tests** passed in the complete post-fix run, and **155 TypeScript tests** passed across Bridge, Panel and Storefront. Repository-wide Prettier, ESLint, Ruff lint/format and all builds passed. Local services were restarted and the original two-line cart was restored exactly. Ticket 15 remains the next evaluation milestone.
