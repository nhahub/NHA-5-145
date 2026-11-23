# LLM interpretation and runtime validation

Approved by the project owner on 26 September 2026 after the [hardcoding audit](hardcoding-audit-2026-09-26.md). Ticket 14 remains on hold until this repair is manually accepted.

## Responsibility

The LLM owns natural-language meaning: typos, Egyptian Arabic, Franco-Arabic, negation, quantities and their direction, references, owned outfit context, soft preferences, and clarification. Runtime code must not match shopper words to verb lists, number dictionaries, product aliases or negation patterns to approve or rewrite its meaning.

Runtime checks still verify schema, supported capabilities and catalogue property kinds, currency and numeric bounds, observed target IDs/roles/options, freshness, same origin, sensitive-field exclusion, duplicate rejection and bound confirmation. Canonical capability membership is not a shopper-language dictionary: for example, a material cannot be misclassified as a use case to bypass an exclusion.

Live interpretation requires schema 8. Earlier versions remain readable for persisted state and explicit scripted tests; a live provider cannot select those legacy execution paths. The legacy `/step` endpoint is unavailable outside scripted configuration. Ordinary scripted browser tests remain explicit execution fixtures; they are not language acceptance tests.

## Current observations and targeting

The model receives the current semantic Snapshot with visible non-sensitive elements, target IDs, names, groups, allowed form actions, product options/selections and cart quantities. Arbitrary textbox values and Sensitive Fields are excluded. A decision is rejected if the session's Snapshot changes while the model is working.

For a cart operation the model selects an observed button ID, not a name for another parser to resolve. Quantity arithmetic uses the observed current value plus/minus the model's delta. For quantity/removal requests outside the cart, the agent first navigates to the cart, then interprets the original request against that fresh Snapshot. Duplicate delivery of that navigation result does not launch another interpretation. Model clarification remains a question, even if its redundant missing-field label is absent.

Current controlled-store execution still knows form routes and accessible control labels. These are store adapter assumptions, not shopper-language interpretation. General storefront navigation, ranking redesign and free-form recommendation prose are outside this repair.

## Exclusions

Catalogue requirements carry `excluded: true` for forbidden properties. Known products with that property are excluded from suggestions. A positive-only product fact list cannot prove the absence of a material: products whose material is unverified may appear only as labeled alternatives with that gap disclosed, never as verified non-leather matches. Unsupported property/kind combinations cannot reach catalogue evaluation.

## Evidence and evaluation

Run the opt-in real-provider cases with `LLM_LIVE_EVAL=1 python -m eval.semantic_boundary_live`. The runner refuses scripted configuration, caps itself at 14 provider calls per run, preserves the existing provider spending cap, and writes model drafts, validated intent and planned actions under ignored `eval/reports/`. Set `LLM_EVAL_CASE` to rerun one named case. Actual browser execution uses `LLM_BROWSER_SMOKE=1 python -m eval.openrouter_cart_browser`; `LLM_BROWSER_CASE` selects add, quantity, remove or clear without repeating the other paid cases. These fixtures define observed pages and expected outcomes; they do not provide model answers.

The initial ten-case live run passed nine cases. The model correctly requested clarification for two shirt variants, but schema validation rejected its missing-field omission. After allowing that safe question, the focused ambiguity rerun passed. Tested cases include quantity wording and a typo, set versus increase, multiple variants, a negated edit, removal, bulk clear, `مش جلد`, written budgets and a prompt-override request. This is a small sample, not universal language reliability.

The runtime tests cover observed/wrong-role target IDs, fresh-cart interpretation, exact selected-line updates, duplicate results, safe clarification, source privacy, schema downgrade rejection, unsupported catalogue properties and scripted endpoint isolation. Existing confirmation, execution, origin and recovery checks remain. Obsolete tests that expected validators to understand or repair sentences were retired; they must not be restored as keyword gates.

Independent Spec and Standards reviewers identified and verified fixes for canonical capability membership, live schema downgrade and the scripted endpoint. Full workspace results and manual acceptance status are recorded in PROJECT_CHECKPOINT.md.

The actual two-product browser run passed quantity, removal and confirmed clearing. Add initially exposed a representation mismatch: the model used `set` for the product form quantity. Schema 8 now permits that explicit representation, defining it as units to add, while rejecting add/increase and add/decrease. A focused live add rerun passed with exact Undo restoration. The final change passed independent review and focused regression checks. Services were restarted and the saved cart restored; owner manual acceptance is still pending.

## Product continuity repair

Manual testing after cart acceptance exposed a different restriction: `open_product` accepted only the immediately preceding recommendation batch. The session replaced that batch when other tasks completed, and the validator also ignored visible product links. This prevented returning to an earlier product even when its link was on the cart page.

Prompt `intent-v19` receives a bounded recent conversation, the latest recommendation batch, and up to 24 previously observed product identities. Product identity comes only from verified recommendations, current same-origin product links, or the currently observed product page, using the configured product route. The LLM resolves names and references; runtime shares one product-identity check between interpretation and execution. No shopper phrase matching is added. The context is session- and origin-scoped; it does not retain target IDs or mutation permission. Sensitive DOM fields are not added to conversation history. Recent conversation is limited to 12 entries of 500 characters each. Earlier product identities can be evicted after the bound is reached, so this is not unlimited memory.

Acceptance covers product opening from the cart without recommendations; reopening an earlier product after navigation, quantity changes, a newer recommendation batch and refresh; and rejecting external, hidden, disabled or unknown product references. Real-model conversation sequences are evaluated separately from fixed model-output execution tests.

Product context observes accepted Action Results and reconciliation snapshots, not just message-start pages. Duplicate product links retain the semantic group label. An unfinished live task is bound to its starting origin; answering or retrying after an origin change is rejected before model invocation. Run the bounded real-conversation acceptance with `LLM_CONVERSATION_EVAL=1 python -m eval.conversation_live`. The initial quantity-outcome failure and the passing eight-turn rerun are recorded separately in ignored reports; quantity field semantics are now documented in the model response schema.

## Exploratory user-flow checks

The owner requested additional messy-user testing before manual acceptance. `LLM_EXPLORATORY_EVAL=1 python -m eval.exploratory_live` runs real browser/model flows with a 12-submission run bound and restores the saved cart. `LLM_EXPLORATORY_CASE` limits reruns to one case. Completion is checked against events for the exact submitted task ID and actual cart contents; prior chat status alone is not accepted as success.

The initial run passed 6/8 cases in nine submitted requests. It caught an arbitrary shirt-size selection and an out-of-range quantity becoming a format error. Negated selective removal plus Undo, bulk-clear cancellation, vague-reference clarification, self-correction without removal, material exclusion plus budget, and spelling variation in product navigation passed.

Prompt `intent-v20` preserves both observed variant labels in product memory and supplies separate cart rows with quantity controls and operation buttons. Navigation memory does not select a cart variant. The model still interprets language and ambiguity; no shopper-word matching is added. The quantity proposal schema permits finite fractional/out-of-range values so runtime can ask a useful question rather than reject the draft. Runtime allows execution only for whole quantities from 1 through 99. Invalid values become an explicit `cart_quantity` clarification with no mutation or model repair call.

Focused live reruns passed the full ambiguous-size/answer/change-of-mind sequence (three requests) and the invalid-quantity case (one request). These are bounded samples, not exhaustive language guarantees. Original failures remain in the ignored `exploratory-user-flows.json` report; focused reports carry the case name. Regression tests separately cover preserved variant information and fractional/zero/negative/oversized quantity proposals at the live HTTP boundary.

## Completion and cart feedback cleanup — 2026-09-27

A follow-up inspection found live completion copy still matching running/shoe words in the raw request. That branch is removed: discovery completion uses the observed result state without inferring product suitability from shopper keywords.

Cart planning now distinguishes correctable input from unavailable page controls. Missing or unavailable options and quantities whose computed total falls outside 1–99 produce editable questions; the answer returns to the LLM with the runtime question and current Snapshot. The planner discards any prepared actions before asking, so an unavailable colour cannot partially change the size first. Missing controls or unreadable current quantities explain why the shopper must stop and refresh. Uncertain mutation outcomes retain their existing Stop-only protection.

Verification: six new HTTP regression cases failed before the fix and passed afterward; 356 Agent and non-browser evaluation tests passed, along with Ruff lint and format checks. Model responses in these tests are explicit fixtures, not live language-quality evidence. No paid calls or service restarts were made. The browser suite was not rerun because its service lifecycle would disrupt the shared demo. The diff was reviewed against the requested cleanup and repository safety rules in this side conversation; independent sub-agents were not used.
