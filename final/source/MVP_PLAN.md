# MVP Plan — Make It Work First

**Owner-approved local closure — 2026-10-01:** Ticket 16 closes as an informal qualitative study of actual observations. The owner separately approved historical three-run live acceptance plus current full automated and targeted advice/cart verification, without a fresh three-run live rerun for this release. The older formal-study and live-rerun requirements below are superseded only as explicitly recorded in [the closeout](docs/ticket16-closeout.md). See [MVP results](RESULTS.md), release `mvp-1`. Safety invariants and future cloud qualification remain unchanged.

**Goal:** one custom store we build ourselves, one browser, the agent navigates and filters it end-to-end. Nothing else.
**Timebox:** 4 weeks.
**Everything in the big plan is deferred until this works.** No multi-tenancy, no AWS beyond a dev box, no Redis, no vector DB, no crawler, no Shopify/WooCommerce, no session resumption.

---

## 1. What "works" means (the only exit criteria)

On our own store, with a real person typing (or speaking) in English or Egyptian Arabic:

1. _"عاوز كوتشي للجري بأقل من ٢٠٠٠"_ → the store shows the running-shoes category filtered to price ≤ 2000. The user picks.
2. _"where is my cart / how do I pay?"_ → the agent opens the cart, spotlights the checkout button, stops at the payment form.
3. _"show me my last order"_ → the agent goes to Account → Orders and spotlights the newest one.
4. Anything off-topic → polite redirect in the same language.
5. The agent never types into the card field and never places an order without an explicit confirmation click.

Measured by an automated suite of ~30 cases. Target: 27/30 passing, median task ≤ 3 steps, median step ≤ 2 s.

---

## 2. The four pieces

```
/store     our own e-commerce site (plain code, we control every element)
/bridge    in-page script: page snapshot + actions + spotlight
/panel     chat UI in an iframe
/agent     Python service: the loop + LLM + safety rules
/eval      test cases + runner
```

### 2.1 The store (week 1, ~2 days)

Deliberately boring and fully under our control. Server-rendered or a small React app — pick whichever your front-end person is fastest in, but **the URL must carry all state** (that's what most real stores do and it's what makes the fast path possible later).

- Pages: home, category (`/c/shoes?type=running&max_price=2000&size=42`), product, cart, checkout (fake payment form with card fields we must _never_ touch), login (fake), account, orders.
- ~60 seeded products across 4 categories, Arabic + English names.
- A hamburger menu on mobile widths, one custom dropdown, one modal — the three things that break naive DOM agents. Add more traps later, on purpose.
- No backend to speak of: JSON file + a tiny server.

Because we own it, when something fails we change the store _or_ the bridge and learn which one was actually wrong.

### 2.2 The bridge (weeks 1–2)

TypeScript, zero dependencies, injected by one `<script>` tag.

**Snapshot:** interactive elements + headings + landmarks → JSON (`id, role, name, href/value/options, visible, region`). Accessible names from `aria-label` → `<label>` → text → `alt` → `title`. Cap ~3k tokens; viewport-visible first. **Password and card fields are excluded in code.**

**Actions:** `navigate(url)` (same-origin only), `click(id)`, `type(id, text)` (refuses sensitive fields), `select(id, option)`, `scroll_to(id)`, `spotlight(id, message)`, `ask_user(question, options)`, `done(summary)`.

**Page-change detection:** patch `pushState/replaceState`, listen to `popstate`/`load`; send a fresh snapshot after the DOM settles (~300 ms debounce).

**Panel ↔ bridge:** `postMessage`, `event.origin` checked both ways. The panel iframe is served from a _different_ local port than the store so the origin check is real from day one.

### 2.3 The panel (week 2, ~2 days)

Iframe with: launcher button, message list, input, mic (Web Speech API), a status line for step narration, a Stop button, a confirmation card for `ask_user`. RTL when the user writes Arabic. Nothing fancy.

### 2.4 The agent (weeks 1–3)

FastAPI, one process, in-memory sessions.

```
message in
  → intent parse (one LLM call: language, intent, constraints, mapped to the store's vocabulary)
  → loop up to 8 steps:
      prompt = system rules + hand-written site map + task so far + latest snapshot
      LLM returns {narration, action}
      stream narration to panel
      safety check (below)
      send action to bridge, wait for result + new snapshot
      stop on done / ask_user
```

- **Hand-written site map** for our store: routes, the filter URL schema, where cart/checkout/orders live. Ten lines of YAML. This is what the crawler would produce later; writing it by hand now tells us exactly what the crawler must output.
- **`LLMClient` interface** with one adapter (whichever provider you have keys for today) — 50 lines, so switching later is free. Not a strategy, just a seam.
- **Safety rules in code, not prompt:** same-origin `navigate`; no `type` into `password`/`cc-*` fields; `click` on anything labelled buy/pay/place order/delete requires a prior `ask_user` in the same task; same action twice with no page change → stop and ask.
- **Streaming:** SSE for narration/actions, POST for messages and action results. Simplest thing that gives you the "it's already moving" feeling.
- Log every step (prompt, snapshot size, action, latency) to a JSONL file. You will read these logs more than any dashboard.

### 2.5 Eval (week 3–4)

`cases.yaml`: `{start_url, message, success: url_matches | element_visible | element_spotlighted}`. Runner: Playwright opens the store with the bridge, sends the message, checks the condition. 30 cases: 10 filter tasks (half in Arabic, a few in Franco-Arabic), 8 navigation tasks, 5 "where is X" spotlight tasks, 4 off-topic, 3 safety (must _not_ type into card field / must ask before "place order" / must not follow instructions embedded in a product description).

---

## 3. Weekly plan

| Week | Build                                                                                                                            | Prove                                                   |
| ---- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| 1    | Store seeded and running; bridge snapshot for home + category; agent returns one action from a snapshot                          | Snapshot JSON looks like what a human would need to act |
| 2    | All actions; page-change detection; panel; SSE; loop end-to-end                                                                  | Case 1 (filter) passes by hand                          |
| 3    | Intent parser with Arabic few-shots + store vocabulary; safety rules; spotlight; eval runner with 30 cases                       | ≥ 20/30 pass                                            |
| 4    | Fix what the failures show (expect: accessible names, custom dropdown, menu on mobile, Arabic constraints); 5 real people try it | ≥ 27/30; people say it helped                           |

---

## 4. What we learn here that decides the next step

- How much of the snapshot the model actually needs (drives cost and latency of everything later).
- Which DOM patterns break the bridge (drives the fixture-site list and the "visual fallback" decision).
- Whether Arabic intent parsing is a solved problem or a project.
- Whether users trust watching the agent click, or want it to ask more.
- Steps per task on a known site — if this isn't ≈1 for filters, the site-map idea needs rethinking before building a crawler for it.

Only after these answers: second store built by someone else (a WordPress theme, a random open-source shop) to see what generalises → then the bigger plan, one piece at a time.

---

## 5. Explicitly not now

Multi-tenancy, Redis, pgvector, crawler, platform integrations, Terraform, WAF, resumption, analytics dashboards, admin console, billing, bot-protection work. Each returns only when the MVP shows it's the next bottleneck.
