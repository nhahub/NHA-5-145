# CAP-02: multilingual evaluation dataset protocol

**Initialized:** 2026-09-29

**Dataset working version:** capstone-v1-draft

**State (6 October 2026):** The owner approved a limited synthetic-pilot exception while leaving final evaluation open. The 40 language-model-generated and 100 Gemini-generated messages now have reviewed draft annotations and a combined conversation/paraphrase map. The [separate frozen pilot](../eval/datasets/capstone-v1/pilot-20261006/README.md) has 82 training / 21 validation / zero unseen cases, with 37 exclusions. It supersedes the earlier tentative 32/8 development allocation for this experiment only. [CAP-03 pilot results](cap03-pilot-results.md) are available. Original intake and final release placeholders remain intact. All data remains synthetic/exposed; draft review is not independent human gold. The owner is the only active contributor, and unseen custody remains unavailable. The final protocol below is unchanged; CAP-02 is not closed.

## Prepared structure

See [the dataset directory guide](../eval/datasets/capstone-v1/README.md). `splits.json` records empty train/validation/regression group assignments and a metadata-only sealed-unseen slot. `case-template.json` is explicitly non-evaluable; null fields mean not annotated. The manifest's existing-source counts are not reviewed split membership. No records were moved into training or unseen evaluation.

The approved [CAP-03 requirements](cap01-requirements.md#graduation-ml-and-deployment-requirements) call for a same-input, intent-only comparison. Annotate whether each case is self-contained and give an eligibility rationale before running models. Context-dependent examples retain sanitized context for a separate contextual benchmark. Fit vocabulary/IDF and other learned transforms only on training data; validation chooses settings, while the custodian-held unseen content stays outside the development checkout until frozen evaluation.

Use [the collection packet](cap02-collection-packet.md) for contributor instructions, permission and custody, and [the label guide](cap02-label-guide.md) for current vocabulary and legacy coverage gaps. The [exposure inventory](../eval/datasets/capstone-v1/exposure-inventory.json) adds explicit `exposed` markers to 104 legacy source-case references and 89 pinned tracked source files; it does not copy private transcripts. Prior debugging chats, screenshots and ignored live reports are exposed by policy even when not individually indexed. Unknown provenance never qualifies as unseen.

## Starting evidence

`eval/datasets/capstone-v1/manifest.json` records source paths, SHA-256 hashes, counts and prior exposure. It does not copy or reinterpret old cases. `eval/intent-corpus.json` contains 60 previously used intent cases; `eval/milestone_cases.py` contains 44 previously used browser scenarios. They measure different seams and can overlap; do not claim 104 unique independent language examples.

Both sources have informed development and evaluation. Treat them as regression/development data, never retrospectively relabel them as unseen. The older corpus mixes language groups and scenario categories in one `kind` field. It therefore cannot establish complete language balance from that field alone. Its schema/labels must be reviewed against the current Structured Intent before reuse; preserving a source hash is not semantic validation.

## Release record and labels

For the next dataset release, each case records:

- Stable `case_id`, dataset version, author/source category, creation date, permission/provenance reference and exposure history. Public records use anonymous contributor identifiers.
- `language_group`: Egyptian Arabic, English, Franco-Arabic, mixed, or other explicitly documented group. Record script separately; do not infer all language metadata from the old `kind` field.
- `scenario_tags`: ambiguity, exclusion/negation, quantity, currency, typo, correction, reference, off-topic, adversarial, and relevant shopping capability; multiple tags may apply.
- Shopper input and ordered follow-up turns; the necessary sanitized Snapshot/context or fixture reference, plus its version/hash. Context-dependent cart references cannot be judged as isolated sentences.
- Expected intent and canonical Constraints, including Money currency/amount, exclusions, quantities/mode, target or acceptable target set, and clarification requirements. Where multiple safe outputs are acceptable, specify them before evaluation rather than adding exceptions after failure.
- `paraphrase_group_id`, `conversation_group_id`, split, and near-duplicate review outcome. All related turns/paraphrases stay in one split.
- Annotation author/reviewer IDs, disagreement/resolution notes and approval state. Separate language interpretation labels from deterministic runtime-safety and browser-outcome labels.

Use the existing canonical vocabulary and evaluator where applicable; adaptation belongs in CAP-03. Do not add shopper phrase matching to production code or change runtime schema to accommodate a benchmark artifact.

## Development and unseen evaluation separation

1. Inventory and review the exposed sources. Retain their existing versions and results as historical evidence.
2. Collect independent, permissioned requests against the supported capabilities, including underrepresented language and difficult cases. Recruitment and real examples require human coordination; initialization does not invent them.
3. Review annotation consistency using development examples. A second reviewer resolves disagreements; report disagreement counts and decisions.
4. Choose the intended coverage, sample size, split groups and acceptance metrics before calling candidate models. The practical sample size depends on confirmed annotation capacity and model budget; no statistically representative sample is claimed at initialization.
5. Have an evaluation custodian hold the unseen cases/labels separately from prompt tuning. Keep related variants and conversations in one split, detect exact duplicates and review near duplicates.
6. Freeze a release manifest with hashes, split sizes, distribution, schema/prompt compatibility and intended use. If an unseen example is inspected to repair the system, record that exposure and use a new untouched set for the next unseen claim; retain the original failure.

Any later study utterances require explicit reuse permission and become exposed once analyzed. Raw participant identities, login/payment fields and private documents never enter the dataset. Synthetic data must be labelled synthetic and not presented as independent participant evidence.

## Evaluation agreement for CAP-03

Report intent classification, exact Constraint agreement, exclusion/quantity errors, clarification accuracy and runtime/browser safety separately, with denominators and per-language/scenario results. Preserve end-to-end task success as an additional measure; model formatting success alone is not task success. Compare candidate configurations on the same released corpus and separate provider outages from interpretation errors. Record token/cost unknowns explicitly and include repairs in accounting.

The historical Ticket 15 44-case gate remains unchanged. The strict Bedrock model-qualification gate remains documented in the graduation scope; the unseen set supplements it rather than silently replacing its denominator. All paid evaluation requires an explicit bounded budget; the current OpenRouter cap stays unchanged.

## CAP-02 completion criteria

- Reviewed dataset labels and provenance, including current schema compatibility.
- A released manifest with stable IDs, source hashes, leakage checks and a genuinely untouched evaluation split.
- Annotation instructions, reviewer/disagreement record, coverage counts and limitations.
- A machine-checkable format and validation command, selected when CAP-02 data packaging is implemented.
- A clear handoff to the existing benchmark in CAP-03, with no paid calls or model-selection claim hidden in dataset preparation.

CAP-02 remains open with initial synthetic development collection prepared. Label review, cross-source duplicate review, the release validator, untouched evaluation collection and freeze remain outstanding. An empty unseen split is recorded as zero, not a completed held-out benchmark. No runtime code, prompt, paid inference or training changes are part of this work.
