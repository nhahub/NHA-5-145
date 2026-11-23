# CAP-02 collection and annotation packet

**9 October 2026 scope amendment:** the owner approved a 120-case synthetic holdout and fixed-model comparison for CAP-02/03 closure, with explicit disclosure that no independent human test set or human label review exists. The original independent-custody requirements below remain historical; [the approved closeout contract](cap02-cap03-closeout-plan.md) governs this release. Synthetic cases remain exposed to their authors/reviewers and are held out from candidate fitting/tuning only. No ticket is closed until that contract is verified.

Started: 2 October 2026. Status: **collection preparation active; no frozen release**.

The owner subsequently prioritized the session refactor and took it on directly. CAP-02 collection is deferred, not complete. Dataset work does not edit runtime interpretation, prompts or execution rules.

## Responsibilities and readiness

The owner clarified that only the owner is an active contributor. There is no available independent human reviewer or team custodian; do not assign those roles to nominal team members or request their help. Any later collection/evaluation design must honestly disclose this limitation. Permission arrangements and available new data remain unconfirmed. No one has been contacted and no historical participant conversation has been imported.

The custodian must not use unseen cases to tune prompts, features, labels or runtime code. A separate annotator and reviewer must agree labels before model evaluation. If the same person must do development and review, disclose this and call the set development/validation data until genuinely independent custody is possible.

We can inventory exposed material and prepare collection now. Final sample sizes, class/language targets and split allocation will be recorded after capacity is confirmed and before candidate runs. Empty splits are not a released dataset.

## Contributor invitation and permission

Use this invitation when the owner is ready to recruit; do not send it automatically:

> We are preparing a graduation-project dataset of shopping requests. Please write requests as you would naturally type them, including your normal spelling, abbreviations and corrections. Egyptian Arabic, Franco-Arabic, English and mixed wording are welcome. You do not need to write in a language you do not normally use. Do not include names, addresses, passwords, card details, private order information or anyone else's messages. Participation is optional.
>
> May we store and publish your anonymized wording and annotations in the project's public research repository for model evaluation? Please choose: public anonymized reuse permitted; private project evaluation only; or no reuse. We will record this choice separately from your identity. Declining does not affect your ability to try the application.

This is a permission prompt, not a claim that permission has been obtained. A public dataset requires explicit public reuse permission; private-only cases stay outside Git. Strip accidental identifying details before ingestion, preserve a record that redaction occurred and seek clarification if redaction changes meaning. Keep the contributor identity/permission register privately, with pseudonymous references in publishable records.

## Eliciting natural requests

Let contributors first explore the supported Storefront and invent their own requests without seeing example phrases or expected labels. Record their original wording before displaying a model response. For guided coverage, offer a goal/context card from the table below and ask how they would express it. Mark that source as **human, scenario-elicited**, rather than spontaneous traffic. Do not supply a sentence for translation or copy-editing.

| Goal/context card                                                            | Coverage purpose                                       |
| ---------------------------------------------------------------------------- | ------------------------------------------------------ |
| Look for something within a budget and one property you do not want.         | Search, price and negation.                            |
| You own an outfit and want help choosing something to go with it.            | Advice, owned-item context and subjective preference.  |
| Two available products look suitable; ask for help deciding.                 | Comparison and uncertainty about unverified qualities. |
| You want to see a product page, then return to an earlier suggestion.        | Product references and conversation context.           |
| A cart has one line; change how many you want, then correct your request.    | Set versus relative quantity and correction.           |
| A cart has several products or two variants of the same product.             | Exact line resolution versus legitimate clarification. |
| Remove something, undo it, then consider clearing the whole cart.            | Reversible change versus Guarded Mutation.             |
| Find the cart/account/orders or ask where checkout is without submitting it. | Navigation versus Spotlight; manual sensitive input.   |
| Ask a shopping question the Storefront cannot answer, or change the subject. | Unsupported capability versus off-topic.               |

Do not force every contributor through every card or manufacture spelling errors. Record which tasks/context they actually used. Browser fixtures, context hashes, cart lines and prior turns must accompany context-dependent requests; no real credentials or payment fields belong in those fixtures.

## Collection procedure

1. Record a pseudonymous contributor ID, source category, date and permission reference. Preserve raw request wording after necessary privacy redaction; do not normalize it into a perfect prompt.
2. Record the supported Storefront/catalogue version and relevant sanitized page/cart/conversation context. Save one conversation as a group; related paraphrases share a group even when their wording differs.
3. Record language group and script independently from scenario tags. A typo, negation or adversarial request is not a language group.
4. Annotate the intended capability and explicit requirements without running a candidate model. Use [the label guide](cap02-label-guide.md). Mark ambiguity and acceptable alternatives rather than inventing intent or requiring one prose answer.
5. Obtain independent review. Keep the first annotation, disagreement and reason for resolution. A draft label suggestion is not independent human verification.
6. Assign development/validation/regression groups only after duplicate review and recorded split policy. Keep all connected conversation/paraphrase groups together, including transitive links.
7. The unseen custodian holds independent requests and labels outside the development checkout. Developers must not read them during tuning. At freeze, publish only permitted metadata, counts, hashes and custody references.

If contributors try the live application while collecting, those requests and any model feedback are **exposed** development material. An unseen collection uses the task context without showing requests or labels to candidate systems/developers before the frozen evaluation. Do not paste unseen content into this chat.

## Exposure and duplicate rules

The [exposure inventory](../eval/datasets/capstone-v1/exposure-inventory.json) marks known legacy cases and tracked development sources as `exposed`. Source-level entries cover their prompts, variants and follow-ups, even when not extracted as individual records. Prior chat debugging, live evaluation transcripts, screenshots and ignored reports are also exposed by policy; the inventory does not claim to enumerate every private artifact.

Absence from that inventory does **not** prove a case is unseen. Independent provenance, custody and review must establish eligibility. Newly generated synthetic examples are synthetic/exposed from creation and never count as independent human requests. Training on selected reviewed exposed data is allowed, but legacy regression scores overlapping that training cannot be presented as independent evidence.

Exact comparisons and normalization can flag duplicates for review; do not replace original text with normalized text. Human review must also consider near-paraphrases, transliteration and shared scenario templates. Group all related cases before allocation; do not randomly split individual conversation turns.

## Freeze checklist

- Confirm contributor capacity, target coverage, total sizes, fixed intent label order and split policy before candidate results are observed.
- Complete permissions, provenance, context, annotation, independent review and disagreement records.
- Audit class/language support and rare/absent classes; never silently merge labels or claim balance from an unreviewed field.
- Validate the machine-readable record contract and all identifiers, group membership, duplicate decisions and source/context hashes. A release validator remains to be implemented before freeze.
- Seal the unseen set with an independent custodian. Store its checksum/count and intended evaluation policy; keep its content outside this development checkout.
- Freeze immutable release files, hashes, compatibility references and limitations. Record any subsequent exposure; never overwrite the original failure or reuse a tuned-on example as unseen.
- Hand the released dataset to CAP-03. No training or paid inference is part of this initiation step.

The current inventory and templates are preparation artifacts. CAP-02 stays open until a reviewed, validated release and genuinely untouched evaluation set exist.

## Synthetic development batch — 2 October 2026

The owner authorized initial synthetic collection after refactoring. The [development collection](../eval/datasets/capstone-v1/development/README.md) now contains 40 language-model-generated examples, ten per requested language group, with draft labels and hashed synthetic context. This establishes `eval/datasets/capstone-v1/development/` as the collection path for exposed development records. Record format 2 extends the old worksheet with explicit cart operation, guarded-mutation kind, catalogue exclusions and semantic notes; the runtime schema is unchanged.

The [grouped split proposal](../eval/datasets/capstone-v1/draft-split-strategy.json) contains 32 training candidates, eight validation candidates and zero unseen test cases. These are tentative assignments, not reviewed release splits. All examples remain synthetic/exposed and unapproved for scoring. The separate [Gemini intake](../eval/datasets/capstone-v1/development/intake/README.md) contains 100 owner-supplied synthetic messages in their original schema; these are not yet mapped or merged. Human collection/review, a released dataset and unseen evidence are not claimed. CAP-02 remains open.
