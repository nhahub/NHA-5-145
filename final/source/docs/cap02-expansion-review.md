# CAP-02 expansion: coverage and review

Prepared during the 6 October 2026 development session under the owner's dataset-first approval. **168 synthetic records added, no new split or experiment run.** They remain exposed, draft and not approved for evaluation. The first pilot's frozen files and 19.05% result are unchanged.

## Deliverables

- [Canonical batch 002](../eval/datasets/capstone-v1/development/synthetic-batch-002.json): 160 primary candidates, four for every intent/language cell; eight additional context-dependent fragments excluded from message-only classification. Total 42 records per language.
- [Family map](../eval/datasets/capstone-v1/development/batch-002-families.json): 40 initial authoring scenarios, reduced to 39 families after merging equivalent clear-cart scenarios.
- [Overlap/revision ledger](../eval/datasets/capstone-v1/development/batch-002-overlap-review.json): 15 known cross-source links, five lexical candidates and their decisions, plus archived wording for twelve revised drafts.
- [Expanded component map](../eval/datasets/capstone-v1/development/expanded-group-map.json): 308 source records in 41 provisional connected components, retaining every original component and all known links. Largest component: 128 records. No component has a split assigned.
- [Audit](../eval/datasets/capstone-v1/development/batch-002-audit.json): coverage and validation evidence. The 26 semantic fixtures live under `development/contexts/batch-002/`; they contain authored assumptions, not observed browser executions.

## Coverage after known links

These counts combine the original 140 rows with the new 168. There are **263 provisional text-only candidates and 45 exclusions**. Component counts describe the current graph; remaining overlap review can reduce them. They do not count independent participants.

| Intent        | Candidate rows | Components with candidate support |
| ------------- | -------------: | --------------------------------: |
| advice        |             33 |                                 5 |
| find_products |             42 |                                 7 |
| locate        |             19 |                                 4 |
| navigate      |             25 |                                 4 |
| open_product  |             18 |                                 4 |
| mutate        |             24 |                                 3 |
| cart_edit     |             46 |                                 5 |
| help          |             18 |                                 4 |
| off_topic     |             17 |                                 5 |
| unsupported   |             21 |                                 8 |

The desired three-training-family/one-validation-family target is **not met for `mutate`**. Do not split the eight clear-cart variants just to manufacture a fourth family. A future pilot must explicitly settle this limitation before allocation: use a justified lower family target with disclosed limits, or add a meaningfully distinct supported scenario. No such change is silently approved here. Feasible row totals alone do not establish a defensible split.

## Spec review

The Spec review checked all 168 initial annotations and 26 fixtures. Three material corrections were made: an ambiguous “drop that condition” follow-up now asks which requirement while retaining existing constraints; university use is preserved as requested but unverified suitability; and an incorrect product-page path was corrected to `/p/clothing-06`. A stale scenario tag on the ambiguous case was also corrected.

## Standards review

The Standards review identified two grouping issues: equivalent clear-cart families and overlap with older cases. They are merged/linked in the expanded graph. Twelve initial product-page variants that merely changed a catalogue name were rewritten before any model run as distinct reference-resolution tasks: ordinal selection, product details from a cart line, and cheapest within a fixed shortlist. Their original authored wording is archived, not silently presented as real-user data. The revised cases and review fixes were rechecked; no unresolved annotation findings remain from these two reviews. The family-coverage limitation remains explicit.

Spec: three substantive findings and one stale-tag cleanup resolved. Standards: two grouping findings resolved. Neither axis establishes independent human gold or final split readiness.

## Examples

| Message                                                                   | Intended interpretation                                                                                       |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| زود عداء النيل اللي فالسلة اتنين كمان، مش خليه اتنين                      | `cart_edit`: increase by two, not set total to two.                                                           |
| Nile Runner elly fel cart khalih 4... la 3 bas                            | `cart_edit`: final corrected total is three.                                                                  |
| checkout froze after i clicked. submit it again? dont charge twice though | `mutate` request; reconcile uncertain prior outcome, never auto-replay.                                       |
| من cart افتح تفاصيل الـ shoes الاسود size 42، مش edit quantity            | `open_product`: cart context resolves the product; no quantity change.                                        |
| لا بلاش الشرط ده                                                          | Contextual follow-up with several possible antecedents; ask which condition. Excluded from text-only scoring. |

## Verification and limits

All new records pass the existing v2 JSON schema. Checks cover unique IDs and exact/normalized text across all 308 rows, the four-per-cell distribution, script tags, family coverage, context/catalogue hashes, follow-up antecedents and transitive group preservation. Normalization for duplicate screening uses Unicode NFKC, casefolding and non-word-run spacing without changing stored messages. Same-language `SequenceMatcher` similarity ≥0.60 produced five review candidates; lexical similarity never determines the intent label. Shared colour/size wording between an add request and a removal request was correctly rejected as a paraphrase link.

All referenced fixture product identities, variants, explicit shortlist prices and the corrected product route were checked against the pinned catalogue/application. Fixtures are not executable DOM Snapshots or assertions of current inventory/Undo eligibility. Runtime guards remain authoritative.

These reviews are separate checks, not independent human gold. These examples were authored after inspecting pilot 1 and must stay development-exposed. This review covered the previous 140 canonical synthetic records; the legacy intent corpus, browser tests and private debugging material also remain exposed and need cross-source review before joint use. The ledger explicitly does not claim exhaustive semantic deduplication.

The existing seven offline experiment regression checks and repository formatting were run for this data-only change. No new runtime test coverage, full application rerun, model-quality result, provider call or deployment is claimed. Runtime code and model prompts remain unchanged.

## Next gate

Finish cross-source adjudication and choose a documented group allocation with actual intent/language support, including a decision on the three-component `mutate` limitation. Freeze a **new** release before another offline fit. The current `eval.freeze_pilot` command still reconstructs pilot 1 only; it does not release this expanded batch. Final independent unseen evaluation and the CAP-03 same-input LLM comparison remain open.
