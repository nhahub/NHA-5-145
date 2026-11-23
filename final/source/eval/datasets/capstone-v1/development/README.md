# Synthetic development collections

## Current expansion

[Batch 002](synthetic-batch-002.json) adds 168 exposed synthetic drafts: 160 text-only intent candidates (four per intent/language cell) and eight contextual exclusions. See [coverage plan](../../../../docs/cap02-expansion-plan.md), [review and remaining gates](../../../../docs/cap02-expansion-review.md), [overlap ledger](batch-002-overlap-review.json) and [expanded component map](expanded-group-map.json). Both batches plus Gemini now contain 308 records and 263 provisional primary candidates. The first pilot remains immutable. The subsequent [second pilot](../pilot-20261007/README.md) freezes 210 training / 53 validation rows after four additional overlap links; see [results](../../../../docs/cap03-expanded-pilot-results.md). This does not change the original draft annotations or final release gate.

## Original batch 001

Created 2 October 2026 at the owner's request. [synthetic-batch-001.json](synthetic-batch-001.json) contains **40 language-model-generated draft examples**, ten each in Egyptian Arabic, Franco-Arabic, English and mixed language. They imitate informal phrasing; they are not observations from real shoppers or independent participant evidence.

Every record is `synthetic`, `exposed`, `draft_unreviewed` and `eligible_for_evaluation: false`. Generation and initial annotation share an author. Automated checks and a second review do not constitute independent human annotation. CAP-02 remains open.

## Record format

The batch retains the provenance, input, grouping, comparison and annotation fields of [the version-1 worksheet](../case-template.json). **Record format 2** adds four fields inside `expected`: `cart_operation`, `mutation_kind`, `catalogue_requirements` and `semantic_notes`. Exclusions use the runtime CatalogueRequirement shape; cart operation and guarded-mutation kind use the existing capability vocabulary. `constraints` uses the existing IntentConstraints fields. The [development schema](record-format-v2.schema.json) documents this shape.

This is an annotation format, not a full schema-9 Structured Intent reply and not a browser replay format. `acceptable_targets` contains semantic product IDs, cart-line keys or destinations when needed, never fabricated DOM IDs. For an ambiguous request it stays empty until clarification; candidate variants appear in its context. `quantity` and `quantity_mode` preserve requested delta versus total. `semantic_notes` records required interpretations and safety expectations without demanding exact prose.

Each record represents **one Shopper turn**. Related turns have the same conversation group and are separate records, so `followup_turns` stays empty rather than duplicating scored inputs. Context files store necessary prior turns and synthetic outcomes. A prior outcome is an assumed fixture state, not an observed model result. Later turns in the batch occur in their explicit contextual state regardless of whether a candidate succeeds on earlier turns.

The thirteen files under `contexts/` are synthetic semantic fixtures tied to a Git catalogue revision/hash. They contain no real payment details or private participant data and are explicitly not Snapshots. They make reference labels inspectable; a future browser runner must separately build and verify real observations. Context hashes cover UTF-8 bytes with CRLF normalized to LF, including a terminal newline. All fixture files are saved with LF.

`intent_only_eligible` addresses **only top-level text classification**. Explicit commands may have a clear intent label even though resolving their product/variant needs context; full structured extraction must use that context. Four follow-up fragments are excluded from text-only comparison. No record is currently approved for evaluation, regardless of this eligibility flag.

## Draft splits

The [split proposal](../draft-split-strategy.json) allocates **32 development training candidates and eight validation candidates**, with **zero unseen test cases**. Records' actual `grouping.split` fields and the release [splits.json](../splits.json) remain unassigned/empty pending label and duplicate review. The proposal is not a frozen release.

Allocation uses whole paraphrase families and conversation groups. All connected groups must stay together, including transitive connections and similar cross-language requests. Near-duplicate review against legacy data may require additional merging or removing cases; exact string uniqueness does not establish independence. The proposal is intentionally not presented as statistically balanced: several classes have very few examples and some have no validation support. Forty examples are a development seed, not sufficient evidence of ten-class quality.

Train-only vocabulary/IDF fitting and validation-only model selection apply after review. Unseen test collection is a separate future step, outside the development checkout, with documented custody and limitations. None of these exposed examples may be renamed unseen. If independent unseen collection is unavailable, report that gap rather than invent a holdout claim.

## What was checked

Before commit, check the record shape and runtime label/Constraint vocabulary, 10-per-language distribution, unique case IDs/text, context hashes, predecessor consistency and proposed group isolation. Catalogue type/variant annotations should agree with the pinned catalogue. A second review may find label ambiguities, but labels remain draft until the owner reviews them. No training or candidate-model inference is part of generation.
