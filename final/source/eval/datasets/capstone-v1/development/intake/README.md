# Gemini batch 001 — unreviewed intake

The owner supplied this file and confirmed on 2 October 2026 that Gemini generated it. [The original file](gemini-batch-001.original.json.txt) is retained byte-for-byte; [metadata](gemini-batch-001.metadata.json) records its checksum, source counts and limitations. It is synthetic, exposed and not approved for training or unseen testing. Its original six-field schema is intentionally not presented as CAP-02 record format 2.

It contains 100 unique texts/IDs: 25 Arabic, 25 Franco-Arabic, 25 English and 25 mixed messages, in 28 conversation groups. This is useful additional annotation material. Language counts are supplied tags, not a completed linguistic review. It should not be merged into the 40-record annotated draft until the work below is complete.

## Required annotation work

- Map source labels individually to current intents. `search_product` usually maps to `find_products`; `product_advice` needs review against advice/availability/unsupported requests. `filter_negation` is a modifier, not a standalone runtime intent.
- Distinguish `checkout` navigation from guarded fictional submission. Do not automatically map all eight checkout-labelled messages to one operation. Several include unsupported cash-on-delivery, coupons, messaging or real delivery requests.
- Preserve multi-action requests. IDs 11 and 61 ask to remove and replace an item; their original removal-only labels omit part of the request. IDs 36 and 86 request variant changes, which must not be silently mapped to quantity changes.
- Add context for “first one,” “this,” “the last item” and unresolved variants: observed products, assistant replies and cart state are absent. Group IDs alone do not make these requests executable.
- Keep unsupported or unverified facts explicit. Unknown materials, fit, shrinkage, delivery duration and brands must not become catalogue facts. ID 98 requests order cancellation and cart restoration, outside the current supported capabilities.
- Review cross-language scenario similarity. Groups 5/11/18/25 all follow view-cart then clear-cart; groups 2/16 and 3/17 have similar sequences. Original conversation IDs are insufficient protection from paraphrase leakage.
- Record explicit constraints, review decisions and ambiguity before candidate model runs. Do not force every message into a single text-only classifier example.

There are no exact repeated texts within this file. That does not establish independence or absence of semantic duplicates, either internally or against the existing exposed material. No performance result, human observation, label approval or frozen split is claimed by accepting the file into intake.

The `.json.txt` suffix preserves the supplied bytes outside automatic JSON formatting; its contents are still JSON and can be loaded with a JSON parser.
