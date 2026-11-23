# Shopping Copilot local MVP results

Date: 2026-10-01. Local MVP release: **`mvp-1`**, accepted under the owner-approved scope and release-evidence adjustments.

## Scope and acceptance basis

This release demonstrates multilingual shopping assistance on one Controlled Storefront: catalogue discovery and advice, navigation and Spotlight, cart edits and Undo, and guarded fictional checkout. It uses an in-memory cart/session runtime and fictional products, accounts and payment flows. It does not demonstrate arbitrary retailer compatibility, AWS deployment or production readiness.

The owner approved Ticket 16 as an informal qualitative study on 2026-10-01. The original formal participant-count/task-completion/findings requirements are superseded explicitly in [the study closeout](docs/ticket16-closeout.md), not reported as passed. Runtime safety requirements remain intact.

The owner also explicitly approved using the historical three-run acceptance set plus the current full automated suite and final targeted advice/cart checks for this release. Three full live runs were not repeated after the advice changes; the corresponding release-only exception is documented in the closeout. Future cloud qualification requirements are unchanged.

## Historical full live acceptance

Ticket 15 passed its unchanged three-run gate on frozen source `dd4d897`, intent prompt `intent-v25`, schema 8 and OpenRouter `google/gemini-2.5-flash`. The [full results](docs/ticket15-replacement-results.md) contain case-level outcomes, provenance and measurement definitions.

| Metric                                           | Run 1           | Run 2           | Run 3           |
| ------------------------------------------------ | --------------- | --------------- | --------------- |
| Task outcomes                                    | 43/44           | 44/44           | 44/44           |
| Designated safety outcomes                       | 19/19           | 19/19           | 19/19           |
| Browser Action P50 / P95, ms                     | 305.0 / 682.1   | 305.8 / 677.7   | 309.4 / 680.3   |
| First Action including model, P50 / P95, ms      | 3089.8 / 5591.2 | 2549.6 / 5869.2 | 2597.6 / 5535.2 |
| Fully understood filters completed in one Action | 85.7%           | 100%            | 100%            |
| Median navigation Actions                        | 1               | 1               | 1               |
| Provider calls including repairs                 | 59              | 57              | 57              |
| Attributed call cost, USD                        | 0.06347532      | 0.05864084      | 0.05398930      |

Run 1's mixed-language failure remains included. The full set cost $0.17610546. Dividing by 132 scheduled cases gives about $0.001334 per scheduled case; two cases per run are Bridge-only, so this is not a model-only price or a forecast for advice conversations. Advice can require an additional model call.

Interaction-trap coverage includes mobile controls, URL/component SPA navigation, clarification, duplicate/stale results, refresh/reconnect, Undo expiry, sensitive-field exclusion, prompt injection and bound Confirmation. Browser and model time are reported separately. See the case table in the linked report rather than interpreting aggregate success as coverage of every possible phrase.

## Advice extension and final checks

The final release uses schema 9, `intent-v28` and `advice-v3`, with schema 8 compatibility. Advice is read-only, grounded in fresh bounded catalogue evidence, and cannot authorize cart or checkout actions. Exact-match explanations preserve verified cards and eligibility. The [implementation record](docs/conversational-advice.md) describes the boundary and fallback behaviour.

The first advice exploration found navigation-context and grounding weaknesses and remains recorded. The [final bounded check](docs/ticket16-closeout.md) exercised natural advice, corrections, unknown facts, product comparison and navigation, then exposed and repaired a cart-context schema error. The restored-context add recheck succeeded with the exact requested variant/quantity. It used eight messages, fourteen calls and $0.0204672 overall; this is not a flawless eight-message run or a replacement for the historical 44-case acceptance set.

Final automated regression results: **458 Python tests and 155 TypeScript tests passed**, with builds/typechecks, lint and formatting passing. Independent Spec and Standards reviews found no actionable issues in the cart repair. No phrase interpreter, relaxed target validation or automatic replay was introduced.

## Human feedback

Five informal testers reportedly explored without owner assistance. After the advice update, all five reacted positively; one explicitly described the assistant as useful for online shopping. Two successful “My account” navigations were reported. All five reportedly lack confidence making purchase decisions online, which differs from low confidence operating interfaces. The two concrete findings were robotic conversation and insufficient comparison/decision support. No numerical ratings, standardized task success rate or additional findings are invented. [Feedback ledger](docs/ticket16-feedback.md).

## What we learned

1. **Snapshot size and cost:** bounded semantic observations support the demonstrated controlled-store journeys. These tests do not establish a globally minimal snapshot or an optimal latency/cost configuration.
2. **DOM patterns:** explicit navigation/settling, grouping and stale-action checks address the tested interaction traps. Independent-store generalisation remains untested and deferred.
3. **Arabic interpretation:** Egyptian Arabic, Franco-Arabic and mixed input worked across many recorded cases, but interpretation is not solved. Semantic substitutions and malformed proposals still occur; retained failures and targeted repair evidence make this visible.
4. **Shopper trust and usefulness:** the positive informal feedback supports perceived value of decision assistance. It does not establish a measured preference about confirmation frequency, comparative efficiency or population-level trust.
5. **Steps per task:** the frozen full gate achieved one Action for all fully understood filters in runs 2 and 3, with median navigation one Action. Component-only SPA cases required more interaction; advice adds model work without authorizing browser Actions.

## Limitations and next work

Known advice limitations include internal misclassification of an owned garment and an unsupported suitability tag, plus a warmth implication without an explicit catalogue fact. The advisor correctly acknowledged unknown washing quality and standing comfort in the final check, but free prose remains probabilistic. Empty-cart live verification was not reached in that check; current automated and historical live safety evidence are reported separately.

Next is CAP-01: confirm graduation deliverables, owners, deadlines and evidence references. CAP-02 prepares reviewed multilingual data and untouched evaluation splits; CAP-03 trains the approved offline classical baseline and compares intent classification fairly with the LLM. The baseline never replaces the runtime interpreter. Controlled Storefront AWS work follows its separate design, budget, model and deployment gates.
