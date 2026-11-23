# Proposed CAP-02 / CAP-03 closeout — 9 October 2026

Status: scope amendment and maximum $0.20 experiment allowance approved by owner on 9 October 2026. Completed under the approved amendment; see [closeout evidence](cap02-cap03-closeout.md).

## Current evidence

The existing development pool contains 308 synthetic/exposed records. The second
pilot freezes 263 eligible records as 210 training and 53 validation, with zero
unseen test records. Seven classifier families and 46 configurations were evaluated;
validation was used for selection. These results must retain their exploratory label.
Existing frozen data, predictions and reports must not be overwritten.

The original CAP-02 completion condition requires an independently held untouched
evaluation split and reviewer evidence. Only the owner is active;
independent human collection/review is unavailable. A synthetic holdout is a revised
academic scope, not fulfillment of the original independent-data requirement.

## Proposed amended completion contract

Close CAP-02 as a versioned synthetic multilingual benchmark and CAP-03 as a
reproducible comparison on a fresh synthetic holdout. Disclose generator provenance,
draft annotation, owner review, small sample size, generator bias and absence
of independently collected shopper evidence. No real-world generalisation claim.
Owner approval was received before execution. Owner scope approval is not a claim of per-record human label review.

1. Freeze hashes for the existing seven selected classifier artifacts/configurations,
   label definitions, short text-only LLM classification prompt and scoring policy
   before constructing or inspecting new evaluation outputs. Do not retune models.
2. Target 120 new text-only eligible requests: three examples per ten-intent/four-
   language cell. Preserve messy phrasing, negations and corrections. This is a
   bounded coverage target, not a statistical adequacy claim. Context-dependent
   requests belong in a separately reported set, not the primary comparison.
3. Record synthetic provenance and exposure accurately. Review labels before model
   predictions; retain ambiguities/exclusions and their reasons. Group related
   paraphrases/conversations together. Audit exact/near overlap with development,
   regression cases and accessible prior debugging material; disclose incomplete
   private-history coverage. Resolve overlap before freezing the new holdout.
4. Freeze dataset, labels, groups and protocol hashes. Keep this set out of fitting,
   model selection, prompt development and application debugging. Once evaluated,
   report it as consumed evaluation evidence; no score-driven rewriting or reruns.
5. Evaluate the seven previously selected classifiers and the pinned LLM on the
   same text-only inputs and label vocabulary. No catalogue, cart, hidden context or
   extra examples for one contender. One LLM attempt per example, no repair retries;
   invalid output/provider failures remain visible and count in the denominator.
6. Publish predictions, accuracy, macro/per-class F1, language slices, confusion
   matrices, error analysis, and measured single-request latency/cost. Distinguish
   classifier text-to-label evaluation from full shopping-agent competence/safety.
   Update the results notebook and rerun instructions. Preserve weak results honestly.
7. Close tickets only after release validation, results verification and the amended
   criteria are met. Record independent human/real-shopper evaluation as a limitation
   outside the amended closeout, never as evidence that was collected.

## Proposed paid comparison allowance

Request a maximum of $0.20 additional API usage from the existing prepaid balance,
within the unchanged $2 total non-resetting key cap. This is a proposed experiment
allowance, not permission to deposit funds, raise a cap or enable auto top-up.
Before dispatch, verify current remaining allowance and implement conservative
per-request reservation against the experiment allowance. Stop before exhaustion;
report partial results rather than silently extend the allowance. Offline classifier
runs use local hardware. No AWS resource is needed for this closeout.

## Alternative retaining the original criteria

Keep CAP-02/03 open until genuinely new evaluation material and a defensible
independent collection/review arrangement are available. Do not rename reused
validation data as unseen or treat a non-independent review as independent human gold.
