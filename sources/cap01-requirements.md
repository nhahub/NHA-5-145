# Requirements gathering and traceability

**Project:** Shopping Copilot. **Updated:** 16 October 2026. **Track:** AWS ML Engineering. **Published DEPI deadline:** 16 October 2026. **Status:** prepared for submission under the [supplied content guidelines](depi-guideline-alignment.md). Lecturer approval and the repository invitation are owner-confirmed; a dated approval reference and official upload record have not been supplied.

**Actual working arrangement (2 October 2026):** the owner and coding assistant perform the work; the owner coordinates this deliverable. Earlier named academic leads were administrative allocations, not verified contributions or available staffing. See the updated [CAP-01 register](cap01-execution.md).

## Problem and stakeholders

A Shopper may know what they want but struggle to choose among products or translate a request into filters, navigation and cart controls. The project addresses both decision assistance and execution on one Controlled Storefront. It must support natural multilingual input while preserving the Shopper's control over consequential actions.

Stakeholders are the Shopper, the project team maintaining the catalogue/application, and the DEPI reviewers assessing the graduation deliverables. Team technical roles and confirmed dates are recorded in [the CAP-01 register](cap01-execution.md). The deployment is a controlled graduation demonstration with fictional commerce data, not a service connected to real retailers or payment providers.

## Elicitation sources and their limits

| Source                                                    | What it establishes                                                                                          | Limitation                                                                                          |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| Owner-approved local specification and domain model       | Supported journeys, controlled scope and safety invariants                                                   | Earlier wording is superseded where later owner decisions are explicit.                             |
| Informal feedback from five testers, relayed by the owner | Positive reactions to advice; two successful account navigations; demand for natural styling and comparisons | No standardized scores, complete task matrix or measured comparative benefit.                       |
| Owner observations and approved changes                   | Need for exact-match explanations, conversational follow-up and model-owned interpretation                   | Individual reports are not population-level research.                                               |
| Runtime tests and live reports                            | Concrete observed successes, failure modes and guarded behaviour                                             | Coverage is finite and tied to recorded configurations.                                             |
| Owner-supplied DEPI schedule and team table               | Applicable dates and assigned technical roles                                                                | The images do not establish official rubric weights or a document template.                         |
| Five supplied DEPI PDFs, reviewed 2 October               | Required documentation content, infographic, organization GitHub delivery and confirmed dates.               | Literature/lecturer heading discrepancy; grading weights and actual repository access not supplied. |

All five testers reportedly lacked confidence choosing purchases online; this is not evidence that all had difficulty operating website controls. The recorded findings were robotic responses and insufficient comparison/decision support. UI comments were not supplied in detail and are not invented as requirements. The approved informal study and technical release exceptions are fully recorded in [Ticket 16 closeout](ticket16-closeout.md).

## Functional requirements

### User stories and use-case mapping

These stories express requirements rather than quotations from participants. Detailed preconditions, alternative flows and observable outcomes are in the [design use cases](system-analysis-design.md#3-use-cases).

| Story | Shopper goal                                                                                                    | Requirement / use case | Acceptance example                                                                                   |
| ----- | --------------------------------------------------------------------------------------------------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------- |
| US-01 | As a Shopper, I want to express budget, size and exclusions in my own language so I can find suitable products. | FR-01–02 / UC-01       | Preserve explicit exclusions; unknown facts cannot qualify a product as an Exact Match.              |
| US-02 | As a Shopper, I want to discuss trade-offs so I can make a more informed choice.                                | FR-03 / UC-02          | Compare verified facts, label styling opinions, acknowledge unknown qualities; no mutation.          |
| US-03 | As a Shopper, I want to open an identified product or find a control so I can continue shopping.                | FR-04 / UC-03          | Navigate only to supported observed destinations; Spotlight does not submit checkout.                |
| US-04 | As a Shopper, I want to edit one cart line and undo a mistake so other items stay unchanged.                    | FR-05 / UC-04–05       | Resolve the exact variant; distinguish added quantity from total; preserve the original Undo expiry. |
| US-05 | As a Shopper, I want to approve the precise effect before clearing the cart or submitting fictional checkout.   | FR-06 / UC-06          | Changed cart state or expired/reused Confirmation cannot authorize the effect.                       |
| US-06 | As a Shopper, I want account/order guidance while entering private details myself.                              | FR-07 / UC-07          | Sensitive values are excluded from observations and model requests.                                  |
| US-07 | As a Shopper, I want to stop or refresh without accidentally repeating a cart operation.                        | FR-08 / UC-08          | Reject stale results and reconcile uncertain outcomes before any further effect.                     |
| US-08 | As a Shopper, I want to review dictated text before sending it and type when speech is unavailable.             | FR-09 / UC-09          | Transcription is editable; recording/availability failures do not block typing.                      |

### Functional acceptance

Priority **Must** means required within the approved graduation scope; it does not imply every future cloud or ML requirement is already implemented.

| ID    | Requirement                                                                                                                   | Observable acceptance and evidence                                                                                                           | State                                                                           |
| ----- | ----------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| FR-01 | Interpret Egyptian Arabic, Franco-Arabic, English and mixed-language shopping requests, including corrections and references. | Evaluate labelled intent/Constraints separately from completed browser tasks; report failures by language/scenario.                          | Local implementation/evidence exists; new dataset evaluation planned.           |
| FR-02 | Discover available products using explicit requirements, budget, size, colour and ordering preferences.                       | Verify catalogue eligibility; distinguish Exact Matches from Alternatives with named unmet or unknown requirements.                          | Implemented and tested locally.                                                 |
| FR-03 | Provide natural advice, relevant comparisons and concise reasons for exact matches using verified catalogue facts.            | Opinions are distinguishable from facts; absent qualities remain unknown; ask a useful question when needed without forcing a questionnaire. | Implemented; qualitative evidence and known grounding limitations recorded.     |
| FR-04 | Navigate or Spotlight the requested Storefront destination and open an identified product.                                    | Use current observed targets and same-origin destinations; do not confuse locating a control with activating it.                             | Implemented and tested locally.                                                 |
| FR-05 | Add a selected available variant, change quantity, remove a line and offer ten-second Undo.                                   | Assert exact variant/quantity and unaffected lines; Undo restores the precise prior state while its original deadline remains valid.         | Implemented; automated and recorded live checks.                                |
| FR-06 | Require fresh, bound, single-use Confirmation for bulk clearing and checkout submission.                                      | Unconfirmed, expired, mismatched or reused authorization cannot mutate state.                                                                | Implemented; current regressions and historical live evidence.                  |
| FR-07 | Support account/order guidance and newest-order Spotlight without handling sensitive login/payment fields.                    | Shopper enters sensitive values directly; agent acts only on permitted controls.                                                             | Implemented; two reported account navigations are a narrower human observation. |
| FR-08 | Support Stop, refresh reconciliation and task ownership across tabs.                                                          | Discard late/stale Actions and do not replay an uncertain mutation automatically.                                                            | Implemented and tested locally.                                                 |
| FR-09 | Offer readable chat, RTL/localization, product cards and editable speech input when the selected service is available.        | The Shopper can type when speech is unavailable and can review transcription before sending.                                                 | Implemented; paid voice currently constrained by provider-key allowance.        |

All functional requirements above are Must within supported local capabilities. They do not extend the catalogue to laptops merely because a participant used laptops as a comparison example.

## Safety and quality requirements

| ID    | Requirement                                                                                           | Verification approach                                                                                                                     |
| ----- | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| SQ-01 | The LLM owns interpretation; validation must not become a shopper-language keyword/regex interpreter. | Inspect boundaries and test schema/target/quantity failures independently from live language-quality cases.                               |
| SQ-02 | Reject off-origin navigation and exclude Sensitive Field values from model context.                   | Adversarial browser and deterministic policy regressions.                                                                                 |
| SQ-03 | Validate inventory, quantity/price bounds, observed targets and exact mutation authorization.         | Public API, Bridge and Storefront regression checks, including stale and duplicate attempts.                                              |
| SQ-04 | Preserve truthful evidence and safe fallback.                                                         | Retain failures, unknown usage and original artifacts; malformed advice preserves verified cards without retry loops or mutation.         |
| SQ-05 | Measure latency, task steps and cost with explicit denominators.                                      | Separate model-inclusive time from browser execution; count repairs and do not substitute estimates for missing billing.                  |
| SQ-06 | Prevent credential and participant-data disclosure.                                                   | Keep environment files/secrets out of Git, omit personal contacts from public reports, and obtain authorization for recording/data reuse. |
| SQ-07 | Keep advice read-only and resistant to untrusted instructions in product text.                        | No executable fields/tools in advice responses; later action requests re-enter normal execution guards.                                   |

Current evidence is summarized in [RESULTS.md](../RESULTS.md). The historical 44-case full-model gate and its performance definitions remain tied to its frozen runtime. The local release uses the owner's explicit evidence exception; it does not prove every paraphrase, product claim or browser interaction is correct.

## Graduation ML and deployment requirements

| ID    | Requirement                                                              | Planned acceptance                                                                                                                                                              |
| ----- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GR-01 | Release reviewed multilingual data with provenance and exposure history. | CAP-02: documented labels, reviewer decisions, group-aware splits and an untouched evaluation set.                                                                              |
| GR-02 | Train an offline classical baseline and compare it fairly with the LLM.  | CAP-03: TF-IDF + Logistic Regression, train-only learned transforms, validation-based selection, same eligible inputs, confusion matrices and error/cost/latency analysis.      |
| GR-03 | Deploy the Controlled Storefront application on AWS.                     | CAP-04–07: reviewed budget/design, qualified model, protected deployment, operational acceptance and repeatable recovery/rollback evidence.                                     |
| GR-04 | Qualify the AWS model before relying on it for actions.                  | The approved gate retains 100% schema/currency/safety compliance and at least 95% exact intent-and-Constraint accuracy on its defined corpus; report unseen results separately. |
| GR-05 | Provide traceable academic and individual evidence.                      | Confirmed owners, deadlines, weekly contribution records and final documentation/demo aligned to the actual DEPI requirements.                                                  |

These are Must graduation requirements beyond the completed local MVP. Offline training and the [seven-family development comparison](cap03-model-comparison-results.md) have been performed on 210 training / 53 validation / zero unseen examples. The best selected validation result was 23/53 correct (43.40%) with macro-F1 0.4304; all data are synthetic/exposed. This fulfills exploratory experiment preparation, not independent model qualification or the final LLM comparison. CAP-02/03 final evaluation and AWS delivery remain open. The offline models do not enter the runtime or authorize Actions. Separate evaluation of context-dependent requests avoids claiming that isolated text classification measures full conversational execution.

## Requirements traceability matrix

The matrix links every functional (FR), safety/quality (SQ) and graduation (GR) requirement to its origin, implementation responsibility and verification evidence. Requirement text and acceptance criteria remain defined above; the identifiers provide a two-way lookup from a requirement to its evidence and from an evidence group back to the requirements it covers. All 21 requirements are Must within the agreed scope.

Origin codes: **S1** = owner-approved local specification and domain model; **S2** = owner/tester feedback and Ticket 16 closeout; **S3** = approved graduation scope and ML backlog; **S4** = supplied DEPI documentation/submission guidelines. US identifiers refer to the user stories in this document; UC identifiers refer to the detailed design use cases.

Status codes: **Local** = implemented with recorded local evidence, not a universal correctness claim; **Limited** = locally available with stated capability/provider limits; **Partial** = some evidence exists but the full requirement remains open; **Open** = required future acceptance is not established. The matrix indexes existing records; it does not claim that the tests were rerun for this documentation update or that an informal study proves usability.

### Functional traceability

| Req. ID | Origin / story        | Implementation           | Verification / evidence                                                      | Status  |
| ------- | --------------------- | ------------------------ | ---------------------------------------------------------------------------- | ------- |
| FR-01   | S1; US-01 / UC-01     | M1: intent pipeline      | V1: language, correction and context cases; unseen evaluation pending        | Partial |
| FR-02   | S1; US-01 / UC-01     | M1, M2: discovery        | V2: explicit constraints, stock and Exact Match/Alternative checks           | Local   |
| FR-03   | S1, S2; US-02 / UC-02 | M2: grounded advice      | V2: read-only advice, references and fallback; R2 informal feedback          | Limited |
| FR-04   | S1; US-03 / UC-03     | M3: navigation/Bridge    | V3: observed destination, Spotlight and product-reference cases              | Local   |
| FR-05   | S1; US-04 / UC-04-05  | M4: cart/Undo            | V4: exact variant/quantity, unaffected lines and Undo/refresh cases          | Local   |
| FR-06   | S1; US-05 / UC-06     | M4: Confirmation         | V5: expiry, state binding, cancellation and single-use checks                | Local   |
| FR-07   | S1; US-06 / UC-07     | M3, M5: account guidance | V3, V6: login handback, newest-order Spotlight and sensitive exclusion       | Local   |
| FR-08   | S1; US-07 / UC-08     | M5: session lifecycle    | V7: Stop, lease/takeover, stale/duplicate and refresh/reconnect checks       | Local   |
| FR-09   | S1; US-08 / UC-09     | M6: Panel/speech         | V8: editable input and unavailable-speech fallback; typing remains available | Limited |

### Safety and quality traceability

| Req. ID | Origin / story | Implementation             | Verification / evidence                                                      | Status  |
| ------- | -------------- | -------------------------- | ---------------------------------------------------------------------------- | ------- |
| SQ-01   | S1; US-01      | M1: intent boundary        | V1: model-owned meaning; schema, capability and observed-target checks       | Local   |
| SQ-02   | S1; US-06      | M3: Bridge/privacy         | V6: off-origin and Sensitive Field regressions; cloud checks still required  | Local   |
| SQ-03   | S1; US-04-05   | M1, M4: mutation authority | V4, V5, V7: stock/bounds, Confirmation and stale/duplicate rejection         | Local   |
| SQ-04   | S1, S3         | M2, M7: fallback/reporting | V2, V9; R1: preserved failures, usage unknowns and verified-card fallback    | Local   |
| SQ-05   | S1, S3         | M7: evaluation metrics     | V9: phase timing and usage accounting; R1; cloud workload still open         | Partial |
| SQ-06   | S1, S4; US-06  | M3, M6; data handling      | V6, V8: sensitive exclusion; R2: privacy limits; cloud/data processes remain | Partial |
| SQ-07   | S1; US-02      | M2: read-only advice       | V2: no executable advice fields; later mutations re-enter normal guards      | Local   |

### Graduation traceability

| Req. ID | Origin / story    | Implementation            | Verification / evidence                                                                       | Status  |
| ------- | ----------------- | ------------------------- | --------------------------------------------------------------------------------------------- | ------- |
| GR-01   | S3; CAP-02        | M7: dataset releases      | R3: synthetic grouped releases exist; independent reviewed unseen set absent                  | Partial |
| GR-02   | S3; CAP-03        | M7: offline ML            | V10; R3: 46 exploratory fits; independent final LLM comparison pending                        | Partial |
| GR-03   | S3, S4; CAP-04-07 | M8: AWS delivery          | R4: design/cost constraints only; deployed journey and cloud acceptance pending               | Open    |
| GR-04   | S3; CAP-05        | M8: Bedrock qualification | R4: strict model gate specified; no qualified AWS model result recorded                       | Open    |
| GR-05   | S3, S4; CAP-01/08 | Academic delivery process | R5: reports, assigned roles and owner approval/access record; upload/contributions incomplete | Partial |

### Implementation reference key

- **M1:** `agent/llm/intent_pipeline.py`, `agent/llm/intent.py`, `agent/discovery.py` and `agent/planner.py` interpret and validate supported shopping intent and plan bounded Actions.
- **M2:** `agent/catalogue.py` and `agent/advice.py` ground product results and read-only advice in catalogue evidence.
- **M3:** `agent/navigation.py`, `agent/product_reference.py`, `bridge/src/snapshot.ts`, `bridge/src/actions.ts` and `bridge/src/runtime.ts` provide destination/target checks, Snapshot privacy and browser execution.
- **M4:** `agent/cart.py`, `agent/confirmation.py`, `store/src/guarded-cart.ts` and `store/public/cart.js` implement cart authority, Confirmation and Undo.
- **M5:** `agent/sessions.py`, `agent/session_registry.py`, `agent/session_state.py`, `agent/session_stream.py` and `panel/src/event-stream.ts` coordinate task/session state and event delivery; the session facade delegates shopper commands and ActionResult/recovery processing to task modules.
- **M6:** `panel/src/panel.ts` and `agent/speech.py` provide the interaction panel and bounded speech service/fallback.
- **M7:** `eval/intent_benchmark.py`, `eval/baseline_pilot.py`, `eval/measurement.py`, `eval/milestone_report.py` and `eval/datasets/capstone-v1/` hold offline data/ML experiments and evaluation accounting. These models do not execute runtime Actions.
- **M8:** future AWS adapter, hosting, privacy/isolation and deployment controls are governed by CAP-04-07; this reference is an assigned work area, not implemented infrastructure.

### Verification and evidence reference key

- **V1:** `agent/tests/test_intent_pipeline.py`, `agent/tests/test_semantic_boundary.py`, `agent/tests/test_product_context.py` and the real-model cases in `eval/milestone_cases.py`. Scripted tests verify execution contracts; only recorded real-model runs are language-quality evidence.
- **V2:** `agent/tests/test_catalogue.py`, `agent/tests/test_discovery.py`, `agent/tests/test_advice.py` and `store/tests/catalogue.test.ts`.
- **V3:** `eval/tests/test_ticket08_cases.py`, `agent/tests/test_real_task.py`, `bridge/tests/action-executor.test.ts` and product-reference cases in `agent/tests/test_product_context.py`.
- **V4:** `agent/tests/test_cart_task.py`, `store/tests/reversible-cart.test.ts` and `eval/tests/test_ticket11_cart.py`.
- **V5:** `agent/tests/test_confirmation.py`, `agent/tests/test_guarded_task.py`, `bridge/tests/guarded-mutation.test.ts` and `eval/tests/test_ticket10_guarded_browser.py`.
- **V6:** `bridge/tests/safety-review.test.ts`, `bridge/tests/snapshot-builder.test.ts` and `eval/tests/test_ticket09_safety.py`.
- **V7:** `agent/tests/test_sessions.py`, `agent/tests/test_recovery.py`, `panel/tests/event-stream.test.ts` and `eval/tests/test_ticket14_spa.py`.
- **V8:** `agent/tests/test_speech.py` and `panel/tests/panel-controller.test.ts`.
- **V9:** `eval/tests/test_measurement.py`, `eval/tests/test_milestone_report.py` and `eval/tests/test_usage_reconciliation.py`.
- **V10:** `eval/tests/test_baseline_pilot.py`, `eval/tests/test_group_allocation.py` and `eval/tests/test_model_comparison.py` verify offline experiment integrity, not an independent model-quality score.
- **R1:** `RESULTS.md` and `docs/ticket15-results.md` distinguish local release acceptance, historical live runs, measurements and limitations.
- **R2:** `docs/ticket16-closeout.md` records the actual informal feedback and owner-approved study adjustments.
- **R3:** `docs/cap03-model-comparison-results.md` and `notebooks/cap03-model-comparison.ipynb` document the synthetic/exposed 210-training / 53-validation / zero-unseen release.
- **R4:** `docs/cap04-credit-only-plan.md` and the CAP-04-07 backlog record cloud design/qualification/deployment requirements and outstanding decisions.
- **R5:** `docs/cap01-execution.md`, the supplied-guideline alignment register and the lecturer appendix record academic preparation and owner-confirmed approval/access; an actual official upload commit remains to be recorded.

The public paths above identify implementation and evidence locations, not proof that every requirement is fully accepted. Revisit affected rows when code, dataset release, model configuration, verification or approved scope changes; retain old results rather than silently replacing them.

## Exclusions, assumptions and open questions

Excluded: arbitrary retailers, external store integrations, real transactions, multi-tenant SaaS and general production-readiness claims. The owner created an AWS Free-plan account; a 7 October screenshot showed $100 credits. The deployment constraint is zero out-of-pocket spending. Region/model eligibility, complete hosting/HTTPS costs, isolation, abuse limits and authorized provisioning remain CAP-04 decisions. Test fixtures and local accounts remain fictional; the current in-memory state is not assumed durable after cloud deployment.

The owner coordinates the overall submission and supplied [the organization repository](https://github.com/nhahub/NHA-5-145) on 16 October, confirming both the invitation and lecturer approval were received. No additional approval wording/date or editable report template was supplied. Actual work is performed by the owner and coding assistant; nominal academic roles do not establish independent review. Dataset review/custody arrangements and numerical rubric weights remain unresolved. The published DEPI dates remain recorded; no formal extension is inferred from a relative submission date. Requirement changes should record their source, effect on implementation/evidence and explicit approval; passed tests do not silently redefine a requirement.
