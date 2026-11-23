# Capstone dataset preparation structure

**Current status (9 October 2026): CAP-02 closed under the owner-approved synthetic scope.** The [new release](holdout-20261009/README.md) adds 120 synthetic test messages; earlier training/validation releases remain unchanged. Independent human evaluation is not claimed. See [closeout](../../../docs/cap02-cap03-closeout.md). The historical preparation notes below describe the superseded independent-data gate.

**State (7 October 2026):** CAP-02 final release remains open. Two separately frozen synthetic development pilots exist: [pilot 1](pilot-20261006/README.md), 82 training / 21 validation, and [pilot 2](pilot-20261007/README.md), 210 training / 53 validation. Both contain **zero unseen cases**. The expanded pool has 308 records, 263 eligible candidates and 45 exclusions. See [current results](../../../docs/cap03-expanded-pilot-results.md) for coverage and limitations.

The owner is the only active contributor; independent human review and unseen custody remain unavailable. All draft annotations remain exposed, synthetic and non-gold. The separate pilot exception does not close final CAP-02. Original intake, first pilot and final empty split placeholder remain unchanged.

- `manifest.json`: hashes and counts of the exposed source corpora; not a released training dataset.
- `splits.json`: empty group assignments and a metadata-only slot for a future sealed unseen release.
- `case-template.json`: a non-evaluable annotation template. Null fields explicitly mean not annotated; it is never a sample or benchmark input.
- `exposure-inventory.json`: explicit `exposed` status for pinned development/test sources and legacy case IDs. Counts are source records, not unique utterances; no labels have been independently approved by this inventory.

The record contract and review process are in [the CAP-02 protocol](../../../docs/capstone-dataset.md). Use the [collection packet](../../../docs/cap02-collection-packet.md) and [label guide](../../../docs/cap02-label-guide.md) before ingestion. The primary classical/LLM comparison is recorded in [the graduation requirements](../../../docs/cap01-requirements.md#graduation-ml-and-deployment-requirements).

## Preparing records later

Review/import permitted source cases into versioned development records. Assign stable case, paraphrase and conversation group IDs. Fill provenance, consent/reuse permission, labels, reviewer decisions and the comparison-eligibility rationale. A record cannot enter a released split with unresolved labels or required context missing.

Keep `train`, `validation` and `regression` membership disjoint for the capstone release; the old regression corpus can remain available independently, but disclose any overlap with training when reporting its legacy scores. Do not aggregate those legacy scores with unseen results.

The evaluation custodian collects and seals unseen messages and labels outside the development checkout. The committed split file stores only count, checksum and release/custody metadata after freezing; do not put unseen text, labels or personally identifying information in this repository during development. At execution, provide an authorized local path to the sealed release without committing it. Pseudonymous custodian IDs refer to the restricted team register.

Before release, validate required fields, unique IDs, supported labels, group isolation, reviewed duplicates, permission, checksum consistency and input eligibility. The synthetic pilots have separate validated loaders and offline training commands; they do not authorize a final unseen release.

See [the first synthetic development batch](development/README.md) for 40 annotated draft records and grouped split proposal, plus the mapped 100-message Gemini intake and 168-record expansion. Pilot assignments live only in their versioned releases; final release assignments and unseen cases remain zero.
