# CAP-02 development coverage expansion — 6 October 2026

Owner authorized the proposed dataset-first next step. This batch is authored after observing pilot 1, so it is **synthetic, development-exposed and adapted to known coverage gaps**. It is not independent evidence. The first pilot's release, protocol, model and results remain unchanged.

The [completed generation and review record](cap02-expansion-review.md) documents actual coverage, pre-fit authoring corrections and outstanding allocation gates against the original targets below.

## Target before generation

Generate 160 self-contained top-level intent candidates: four per cell of ten intents × four language groups. Use four distinct goal/context families per intent, each containing four related language variants. These are authored scenarios, not four independent shoppers or translation-independent samples. Add eight contextual follow-up fragments (two per language) to exercise corrections and references; exclude these fragments from the message-only classifier task.

| Intent        | Pilot 1 train / validation | New primary candidates | Scenario families                                                                 |
| ------------- | -------------------------- | ---------------------- | --------------------------------------------------------------------------------- |
| advice        | 16 / 1                     | 16                     | colour coordination, price trade-off, use suitability, size uncertainty           |
| find_products | 23 / 3                     | 16                     | shoes, clothing, bags, electronics                                                |
| locate        | 3 / 0                      | 16                     | checkout control, quantity control, remove control, account entry                 |
| navigate      | 1 / 8                      | 16                     | cart, account, orders, checkout page                                              |
| open_product  | 2 / 0                      | 16                     | named shoe, top, bag, audio product                                               |
| mutate        | 1 / 7                      | 16                     | abandon whole cart, replace whole basket, submit checkout, retry checkout request |
| cart_edit     | 29 / 1                     | 16                     | add a specified variant, quantity delta/total, remove one line, Undo              |
| help          | 2 / 0                      | 16                     | capabilities, composing a request, clarification support, manual control          |
| off_topic     | 1 / 0                      | 16                     | cooking, entertainment, study, weather                                            |
| unsupported   | 4 / 1                      | 16                     | external stores, bargaining, delivery rescheduling, return/refund                 |

These counts improve coverage, not statistical independence. For narrow capabilities such as clear-cart and Undo, surface diversity must not be mistaken for new tasks. Keep related wording grouped and explicitly flag cross-batch overlap.

## Annotation and context

Use the existing v2 development record schema, exact ten-label vocabulary and explicit manual annotations. Preserve informal spelling, correction, negation and mixed language. No production rules, regex interpretation or candidate-model labelling. Use semantic fixtures tied to the current catalogue for product/variant references and follow-ups; fixture outcomes are assumptions, never observed executions. No credentials, participant identities or private messages.

Each primary message has a unique conversation ID unless it has an actual recorded follow-up. Related language variants share a family ID. Do not join unrelated intents into invented shopping sessions merely to organize the file; that caused large connected components in the initial pool. All fragments link to their actual antecedent record and share its groups.

## Review and future splits

Check schema, exact/normalized duplicates, language/intent counts, context hashes, semantic labels and cross-source near-paraphrases against the original 140 rows. Record residual ambiguity and overlap honestly. draft review is not independent human gold; all records keep draft status and evaluation approval false.

The desired next pilot has at least three training families and one validation family per intent, with every language represented on both sides where possible. **Do not allocate yet:** reviewed cross-source links may reduce the number of usable families, especially for narrow actions. A later allocation must operate on the complete connected-component graph, preserve related turns, audit actual class/language support and freeze a new version before fitting. If those gates fail, collect more distinct families or explicitly revise the design; do not cut related groups to hit a balance target.

For now publish the new batch, family/context map and coverage/overlap review. Do not change the frozen first pilot, tune a classifier, run paid inference or claim a new unseen split. CAP-02 final release and CAP-03 final comparison stay open.
