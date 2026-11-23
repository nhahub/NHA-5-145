# 07E Grounded Catalogue Discovery — Stage 1 design for review

**Status:** Owner-approved Stage 1 design, implemented and verified in Ticket 07E on 2026-09-23. The browser evidence and remaining provider-throughput caveat are recorded in `PROJECT_CHECKPOINT.md`.

## Intent and scope

The Shopping Copilot must handle goal-oriented requests, not merely translate them into Storefront filters. It should show two or three grounded options immediately, with a short factual reason, and ask about occasion or style only when the available evidence cannot support a useful choice. It must distinguish an Exact Match from an Alternative and from a Styling Suggestion. A broad result must never be described as satisfying a narrower request.

This is **Stage 1** of the approved graduation sequence: stabilize grounded discovery on the controlled Storefront and finish its three owner-written browser requests. It uses the existing fictional catalogue, curated explicit attributes, simulated EGP prices and availability, and the pinned local model. It introduces no Redis, PostgreSQL, vector store, external commerce catalogue, personalization history, currency conversion, or AWS dependency. Browser Actions and their safety contract remain unchanged.

The later stages are deliberately separate: Stage 2 adds the product/cart/simulated-checkout browser journey under the approved Confirmation, Undo, Sensitive Field, and refresh-recovery requirements; Stage 3 expands the legally usable fashion-and-shoes catalogue and benchmarks retrieval; Stage 4 deploys and evaluates the proven flow on AWS. Stage 1 must not imply that a cart or checkout route already works: the current Storefront only renders a cart link, with no cart/checkout routes in `store/src/app.ts`. Each stage ends in a working browser demonstration before the next begins.

The three owner-written acceptance requests cover (1) a light summer/beach shirt, (2) black formal leather shoes for a wedding with a non-numeric price preference, and (3) size-43 running shoes suitable for daily workouts and street running. Their exact wording is evaluation input, not a source of new phrase-specific matching rules.

## Why the current flow fails

The Storefront currently holds product seeds in `store/src/catalogue.ts`, not JSON/YAML. It exposes deterministic filters but not public use-case, material, or styling facts to the Agent. The current Structured Intent can represent category, type, size, color, Money, and free text, but not evidence-backed suitability or material. A model can therefore reduce “formal black leather shoes, not too expensive” to `color=black` and the browser can report products even though the omitted conditions were never checked. The live 07E owner-request run demonstrated exactly that failure.

## Domain outcomes

- **Exact Match:** every explicit, non-negotiable product requirement is supported by authoritative catalogue fields for a currently available product. A vague price preference is not silently converted into an EGP limit; the displayed price and ordering make the preference transparent.
- **Alternative:** a real, available product that fails at least one requested hard requirement. The response names each relaxed or unverified requirement and never calls the product a match. An alternative is offered as a choice, not silently substituted into a browser filter.
- **Styling Suggestion:** a real, available product proposed for an open-ended coordination request. The reason is grounded in product fields and conservative, documented compatibility rules. An item the Shopper says they already own is context, not an item to search for or put in the cart.
- **Unverified:** no authoritative field establishes a claimed use, feature, material, size, or availability. Unknown does not mean false, but it cannot support an Exact Match claim. If no responsible options can be offered, say what cannot be verified and ask one concise question.

Two or three options are a target, not a quota. Show fewer when fewer qualify; never pad the list with unrelated products. The Shopper retains control over whether to inspect an Alternative or relax a requirement. Empty results remain honest and may include clearly labelled Alternatives separately.

## Catalogue seam and facts

The Controlled Storefront remains the single source of product truth. Add a versioned, read-only catalogue view backed by the existing fixture data, reachable only at a fixed trusted local Storefront route. The Agent's catalogue reader uses that configured origin; neither Shopper text nor model output can select a URL. The view returns public facts only: stable product ID, bilingual name, category, type, price with configured EGP currency, sizes, colors, availability, and explicit recommendation attributes. It returns no account, cart, payment, or Sensitive Field data.

Add explicit, canonical product attributes to the fixtures. `features` covers verifiable properties such as material, lightweight construction, breathability, or grip. `suitable_for` covers uses such as hot-weather wear, a wedding/formal occasion, daily workouts, or road running. A small `wear_position` or equivalent field distinguishes upper-body pieces from trousers for outfit requests. Attributes are curated fictional catalogue facts, not model-authored claims. An absent attribute means unverified, not an invitation for the model to infer it from a name. Fixture data should contain positive and negative examples, including products that are near misses, so tests prove both exact and alternative behavior rather than merely making the three prompts pass.

The Agent consumes this view through one narrow catalogue-query module interface. The interface accepts validated product requirements and returns deterministic Exact Match candidates, Alternative candidates with named misses, and evidence fields for the displayed reasons. It hides fixture transport, filtering, availability checks, and ranking. Existing Storefront URL filtering remains the fast path for straightforward exact filters; catalogue-grounded discovery handles use-case, material, and styling requests. Do not duplicate the product array in Python or add a hypothetical database adapter.

## Intent and zero-silent-drop

Extend the versioned Structured Intent to represent product role, explicit hard requirements (including material/features and suitability), soft preferences, and owned-item context. Each extracted requirement carries a source span from the Shopper message. The model may interpret the request but may not choose product IDs, claim inventory, invent attributes, or decide whether a product is an Exact Match.

The Intent Boundary validates schema, source spans, canonical values, Money, and coverage before catalogue querying or browser Action planning. A recognized requirement must be represented, marked unresolved, or cause clarification; it may not disappear. General catalogue taxonomy and source-coverage checks are allowed, but the three acceptance sentences must not be added verbatim as special cases. The wedding regression must explicitly prove that dropping `formal`, `leather`, black, or the non-numeric price preference cannot result in a “matching shoes” success. An unsupported or ambiguous qualifier remains unresolved rather than being replaced by a broad filter. This is a bounded guarantee for catalogue-recognized attributes; arbitrary language outside the taxonomy cannot be claimed universally understood.

Treat numeric budgets as hard EGP Constraints under the existing safety rules. Treat “not too expensive” as a soft lower-price preference: order eligible candidates by price and show their actual EGP prices, without inventing a budget ceiling or calling an item objectively affordable. If the preference materially changes which options qualify and cannot be satisfied responsibly, ask for a budget after showing any useful verified choices.

## Response and task flow

1. Interpret the current Shopper message into validated requirements and context. Keep existing Stop, Retry, refresh, lease, and stale-result protections.
2. For simple complete filters, retain the current direct-navigation path. For product-use or styling requests, query the read-only catalogue before claiming a result.
3. Evaluate explicit hard requirements against catalogue facts. Rank available Exact Matches deterministically. If none exist, generate controlled Alternatives by relaxing one named requirement at a time; each candidate carries its actual unmet requirements. For open-ended outfit requests, consider only eligible upper-body products and ground each short reason in actual catalogue attributes or documented compatibility rules.
4. Present at most three verified products in the Panel with a visible label—Exact Match, Alternative, or Styling Suggestion—plus name, price, availability, and one short factual reason. Preserve this structured result in Agent session state so refresh restores it without replaying a browser Action. Do not mutate cart or checkout state as part of suggesting.
5. Ask a concise follow-up about occasion/style only when the evidence is insufficient to choose useful options, or after presenting options if the Shopper wants to refine them. A Shopper choice may then navigate to the corresponding Storefront view through the existing Action path; no new browser authority is granted to model output.

If the catalogue is unavailable, malformed, or stale, the Agent must not emit a broad success or fabricated suggestion. It should pause or report that it cannot verify products, with Retry and Stop where appropriate. The existing visible result-count check remains required after any discovery navigation. Panel suggestion counts and IDs are checked against the catalogue response, not inferred from the model or page prose.

## Franco-Arabic evaluation status

The live browser evaluator currently expects English completion text for a Latin-script Franco case, while the real model may select Arabic narration. The evaluator should assert completion from the Agent's task state and the actual Storefront outcome, not one localized status string. A separate localization check should report the displayed script/language choice so a status-copy mismatch cannot masquerade as a shopping failure. This change does not silently redefine the product's response-language policy.

## Verification and acceptance

- Test the catalogue module at its public seam: known exact candidates, near misses, absence of evidence, availability, size, EGP price, and deterministic ranking. The Storefront's read-only view and Agent parser share a versioned contract test.
- Test the Intent Boundary directly with model outputs that omit wedding material, occasion/formality, color, and soft price preference. Every omission blocks an Exact Match claim and Action rather than broadening silently. Test Arabic, Franco-Arabic, and mixed-language source coverage without hardcoding the three complete sentences into production vocabulary.
- Test the Panel/Agent browser flow for zero Exact Matches with two or three labelled Alternatives, open-ended black-trousers-to-upper-body suggestions, refresh recovery of suggestions, catalogue failure, Stop, and no unexpected cart mutation. Preserve all existing off-origin, Sensitive Field, Confirmation, stale/duplicate Action, and uncertain-refresh regressions.
- Rerun the **same three owner-written requests** through the pinned real-model browser path after implementation. Record model metadata, browser state, candidate IDs, labels, unmet requirements, and visible copy without storing credentials or sensitive data. Success requires grounded exact/alternative labels and no silent requirement loss; merely reaching a category page or showing a nonzero product count is insufficient.
- Deliver a Stage 1 browser demonstration in which a Shopper can see the verified 07E suggestions and explanations for those requests. Product selection may navigate through existing safe Actions, but Stage 1 makes no claim to a working cart or checkout. Cart and simulated checkout receive their own Stage 2 browser gate.
- Run repository format, lint, unit/integration tests, and production build. Do not mark 07E complete until the three owner requests and existing safety tests pass. Intermittent provider latency is reported separately from semantic accuracy.

## Decisions still requiring implementation review

This design intentionally leaves the exact wire shape of the read-only catalogue response, the internal Structured Intent v2 fields, and the Panel suggestion event to the implementation plan. Their invariants above are fixed. Product-fixture values should be curated to support both positive and near-miss evidence; they must not be tailored solely to the three acceptance sentences.
