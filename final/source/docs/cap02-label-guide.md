# CAP-02 label guide and legacy audit

**9 October 2026 scope amendment:** the owner approved a 120-case synthetic holdout and fixed-model comparison for CAP-02/03 closure, with explicit disclosure that no independent human test set or human label review exists. The original independent-custody requirements below remain historical; [the approved closeout contract](cap02-cap03-closeout-plan.md) governs this release. Synthetic cases remain exposed to their authors/reviewers and are held out from candidate fitting/tuning only. No ticket is closed until that contract is verified.

Prepared: 2 October 2026. **Draft annotation policy for review, not frozen gold labels.**

The runtime vocabulary comes from [Structured Intent](../agent/llm/intent.py) at local MVP `mvp-1` (`39ac6d1`), live schema 9. Label the intended capability separately from runtime execution success. Do not modify legacy expected outputs or production interpretation to fit this dataset.

## Primary intent label vocabulary

| Label           | Meaning for annotation                                                                                              | Important distinction                                                                                               |
| --------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `advice`        | Request for a discussion, recommendation rationale or comparison grounded in catalogue evidence.                    | An ordinary search with filters can remain `find_products` even when the application explains its results.          |
| `find_products` | Browse/discover products satisfying interpreted requirements, including supported recommendation/styling discovery. | Do not relabel every natural request for a recommendation as `advice`; discuss ambiguous cases during review.       |
| `locate`        | Identify or Spotlight a control without activating the requested destination/action.                                | Finding the checkout button is not submitting checkout.                                                             |
| `navigate`      | Go to a supported Storefront destination such as cart/account/orders.                                               | A specific product page uses `open_product`.                                                                        |
| `open_product`  | Open a resolved product's page.                                                                                     | Not a cart change; product identity needs evidence.                                                                 |
| `mutate`        | Request a supported Guarded Mutation: clear cart or submit fictional checkout.                                      | The label never grants Confirmation or permission to execute.                                                       |
| `cart_edit`     | Add, change quantity, remove one line or Undo a reversible change.                                                  | Preserve operation and quantity mode separately from intent.                                                        |
| `help`          | Ask for help/clarification when no more specific supported capability is established.                               | Do not use as a catch-all for spelling errors or provider failure.                                                  |
| `off_topic`     | Request unrelated to supported shopping assistance.                                                                 | Different from a shopping request beyond supported capabilities.                                                    |
| `unsupported`   | Shopping intent outside the supported Storefront capabilities.                                                      | Unsupported currency or missing facts can instead be clarification/constraint outcomes; review the actual contract. |

For a message-only baseline, a record needs one reviewed intent label justified by the text under the fixed task definition. Context-dependent, multi-intent or genuinely disputed labels must be adjudicated or excluded from that primary comparison with a reason. Keep them in separately reported contextual/ambiguous evaluation. Never force a single label only to simplify training.

## Interpretation annotations

- Preserve explicit Constraints, exclusions and their scope. An owned garment's colour is not automatically a desired product colour; a soft preference is not a hard requirement.
- Distinguish an amount added/removed from a final quantity. For a requested increase of three from two, annotate mode `increase`, amount `3`; the runtime computes the final five. Keep fractional/out-of-range requests as written and annotate the expected safe response rather than clamping them.
- Record missing context/fields and whether clarification is necessary. Clear language with several possible cart variants may still require clarification; a typo alone does not.
- Record target identity against a versioned sanitized fixture. DOM IDs are observation-local and must not be guessed from product names.
- Record acceptable semantic outcomes before candidate runs. Advice wording has no single gold sentence: evaluate facts, uncertainty, opinion versus assertion, relevance and action isolation separately.
- For corrections, preserve the full ordered conversation and the final intended requirements. Do not erase the original request or treat its follow-up as an unrelated text-only case.

The initial case template is non-evaluable. Its `expected` fields are a worksheet, not a schema-9 model reply. Full structured outcomes can differ in fields such as catalogue requirements, product references, cart operation, quantity mode and revision. A reviewed machine-checkable representation for these outcomes must be finalized before the release validator and freeze; do not claim template validation proves runtime compatibility.

## Language and scenario metadata

`language_group` records Egyptian Arabic, Franco-Arabic, English, mixed or a documented other group. `script` separately records Arabic, Latin or mixed script. Do not infer the whole language group from a few English catalogue names. Annotators must agree a consistent policy and keep uncertain assignments explicit.

Scenario tags can include typo, correction, negation, ambiguity, reference, quantity, unsupported currency, off-topic, adversarial and capability tags. These are orthogonal to language and can be multi-valued. Do not change raw text while tagging it.

## Audit of existing sources

The 60 cases in [the legacy intent corpus](../eval/intent-corpus.json) currently contain:

| Legacy expected intent |  Cases |
| ---------------------- | -----: |
| `find_products`        |     47 |
| `locate`               |      4 |
| `navigate`             |      4 |
| `help`                 |      1 |
| `off_topic`            |      4 |
| **Total**              | **60** |

`advice`, `open_product`, `mutate`, `cart_edit` and `unsupported` have no cases labelled with those intents in this corpus. This is an inventory count, not a judgement that the existing labels are correct. Do not train a ten-class classifier and claim complete class coverage from these 60 examples.

All 60 expected records omit a wire `v` field and contain only the older benchmark expectation fields. They are benchmark comparison targets, not full schema-9 Structured Intent instances. They need semantic re-review and an explicit comparison mapping before CAP-03 reuse; adding `v: 9` mechanically is not a migration.

The legacy `kind` field mixes language categories with adversarial, ambiguous, malformed-budget, off-topic and unsupported-currency categories. The current `expected.dialect` field is also an existing annotation rather than an independently reviewed language label. Neither is proof of balanced coverage.

The 44 [browser scenarios](../eval/milestone_cases.py) include navigation, follow-ups, mutations and browser conditions. Their scenario `kind` values are not the intent classifier's labels. A scenario may contain multiple messages and share wording with the intent corpus; **60 + 44 is 104 source records, not 104 independent utterances**. The exposure inventory records each original case ID without converting browser scenarios into classifier labels.

The wider inventory includes tracked live probes and test sources. No transcripts from the previous informal study have been reconstructed or invented. Their reuse would require explicit permission and would be exposed, not unseen.

## Review ledger requirements

For every proposed released label retain annotator ID, distinct reviewer ID, first label, disagreement, final decision/reason, review date, comparison eligibility and source/context references. Both roles must review meaning from the input/evidence, not accept a candidate model's answer as gold. Unresolved items stay out of a frozen scored split.

CAP-02 initiation verifies source identities/counts/hashes and records this coverage gap. It does not claim independent label review has happened, that new human data exists, or that splits are frozen.

## Synthetic development batch — 2 October 2026

The owner authorized initial synthetic collection after refactoring. The [development collection](../eval/datasets/capstone-v1/development/README.md) now contains 40 language-model-generated examples, ten per requested language group, with draft labels and hashed synthetic context. This establishes `eval/datasets/capstone-v1/development/` as the collection path for exposed development records. Record format 2 extends the old worksheet with explicit cart operation, guarded-mutation kind, catalogue exclusions and semantic notes; the runtime schema is unchanged.

The [grouped split proposal](../eval/datasets/capstone-v1/draft-split-strategy.json) contains 32 training candidates, eight validation candidates and zero unseen test cases. These are tentative assignments, not reviewed release splits. All examples remain synthetic/exposed and unapproved for scoring. The separate [Gemini intake](../eval/datasets/capstone-v1/development/intake/README.md) contains 100 owner-supplied synthetic messages in their original schema; these are not yet mapped or merged. Human collection/review, a released dataset and unseen evidence are not claimed. CAP-02 remains open.
