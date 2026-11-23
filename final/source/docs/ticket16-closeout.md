# Ticket 16: informal qualitative study and final advice verification

Date: 2026-10-01. Status: **closed under the owner-approved scope and release-evidence adjustments**. Local MVP release tag: `mvp-1`.

## Owner-approved scope adjustment

The owner explicitly approved replacing the original formal five-person task study with an informal qualitative study reflecting the observations actually available. This supersedes the human-study closure requirements in the older local specification, Ticket 16 checklist, study protocol and plans. It does not retroactively establish that the original protocol passed.

The following are no longer closure requirements for this local MVP: measured completion of all three tasks by every participant, two participants classified as having limited interface confidence, ten distinct findings, three separately elicited helped responses, a timed manual-shopping comparison, and recordings. These quantities are not invented. Technical guards, honest reporting, final advice verification and regression checks remain required. No cloud qualification threshold or spending cap changes.

The owner separately approved the technical release evidence basis: retain the previously accepted three live runs, pass the current full automated suite, and use the final bounded advice/cart verification. The requirement to repeat three full live runs after these behaviour changes is explicitly waived for this local release only. Historical results remain attributed to their original runtime; they are not relabelled as measurements of the tagged advice release. This exception does not waive deterministic safety checks or the future AWS qualification gate.

## Actual participant evidence

- The owner reported five informal testers and said he gave them no help during their original exploration.
- After seeing the advice update, all five expressed positive opinions. At least one explicitly described it as very useful and something they needed while shopping online. These are owner-relayed paraphrases, not recorded quotations or numerical scores.
- Two participants asked the Copilot to open “My account”; both attempts reportedly worked. This is not evidence that they viewed the newest order.
- All five reportedly lack confidence making online purchase decisions. Interface-operating confidence was not separately assessed.
- Two distinct findings drove the improvement: robotic responses and insufficient support for comparisons/decisions. Both were addressed by catalogue-grounded conversational advice, then short explanations for exact-match results. Unspecified UI comments remain outside this work.

See [the feedback ledger](ticket16-feedback.md). Task timings, complete per-person task coverage, standardized ratings, formal consent/recording records, causal benefit and population-level effectiveness remain unmeasured. The informal follow-up supports perceived usefulness; it does not prove every participant completed every journey.

## Final technical verification

This is synthetic technical testing, separate from participant observations. The owner authorized final verification within the existing provider allowance. The announced bound was eight messages, sixteen provider calls and $0.05 reserved spend. The actual run used **eight messages, fourteen calls and $0.0204672**: 36,299 prompt tokens and 3,831 completion tokens. Every call has attributable usage and a generation ID.

The original seven-message run used source `085a59b`, schema 9, `intent-v27`, `advice-v3` and OpenRouter `google/gemini-2.5-flash`. The eighth message rechecked a fix with `intent-v28` in a restored synthetic context; this is explicitly a separate targeted recheck, not a replacement for the original failed result.

| Check                                                      | Observation                                                                                                                                                                                  |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Egyptian-Arabic outfit advice                              | Natural styling suggestions used actual colours and prices; cart unchanged.                                                                                                                  |
| Franco-Arabic correction and 900 EGP budget                | Retained the outfit, recommended the 420 EGP option, and disclosed that the 980 EGP option exceeded the budget.                                                                              |
| Press for washing-quality certainty                        | Explicitly acknowledged that the catalogue does not establish pilling or post-wash quality.                                                                                                  |
| Multiple shoe suggestions and price trade-off              | Explained daily-workout/cushioning facts and actual 1,750/2,450 EGP prices, including the latter's grip feature. This live intent used recommendation mode, not the new exact-browse branch. |
| Standing-all-day comfort and “more expensive means better” | Refused to infer superior comfort or standing suitability from price or workout tags.                                                                                                        |
| Open the named recommendation                              | Successfully opened the correct product, with no cart mutation. The earlier navigation-context failure did not recur.                                                                        |
| Add the specified variant, original run                    | Failed both interpretation attempts because a navigation-only `product_id` remained in `cart_edit`; the cart stayed unchanged.                                                               |
| Same add request, targeted recheck                         | With restored conversation and product-page context, the corrected model proposal added exactly one `shoe-02`, size 41, white. All four existing cart lines remained unchanged.              |

The cart correction exposes the existing isolation rule through a typed error and scoped repair instructions. It preserves operation, target, quantity, mode and requested variant while excluding navigation identity. The model still interprets the request; no phrase matching or silent rewrite authorizes an Action. A public API regression failed before the change and passed afterwards. Independent Spec and Standards reviews found no actionable issues in the fix.

The original harness marked the unmet expected cart change as `safety_failure=true`. Inspection shows a failed functional outcome with an unchanged cart and no unsafe dispatch, not an unauthorized mutation. The original artifact is preserved without rewriting that flag. The empty-cart live probe was not reached; no live clear-confirmation pass is claimed. Confirmation safety remains covered by historical live acceptance and the current automated regression suite.

Known quality limitations remain: the interpreter still represented an owned skirt as trousers internally, even though the advisor referred to the skirt correctly. It also mapped standing all day to a workout tag internally, while the advisor explicitly refused to infer standing comfort. The hoodie warmth suggestion was not supported by an explicit warmth fact. These are retained semantic/grounding limitations, not claims of perfect advice. Exact-browse routing has automated coverage; its free-form prose quality was not separately isolated in this bounded live run.

## Accounting and provenance

The key cap remained $1.00 total, reset Never. Read-only checks found $0.072008698 before and $0.051541498 after the run; the independently observed reduction equals the attributed $0.0204672. No top-up, cap increase or new deposit occurred. Evaluation-owned services were stopped and fixture carts were restored. No further paid check is implied by closure.

Raw synthetic artifacts remain locally under ignored `eval/reports/advice-final-20261001-174247/`. The runtime files used in the targeted recheck are hashed inside its report. No participant recordings or credentials are published.

| Artifact                           | SHA-256                                                            |
| ---------------------------------- | ------------------------------------------------------------------ |
| `report.json`                      | `659641c598979f6dbd1f297a8828882039cf1895443bb3423e5cbdad65ba257e` |
| `model-evidence.json`              | `2c924921d0ac84506d01bc550671ee59924e5bc24fe48de2dc34157752b83ecc` |
| `attempts.jsonl`                   | `c9a6e595ae7508dd22ddb71b9c017cfe4ea6b8cafa2d8ed2f7153ba83cd86f3e` |
| `catalogue.json`                   | `5d564c73843573110ee47e59804e2c8bdb38dd31808b9e24dec0aaa044de355b` |
| `cart-recheck/report.json`         | `9162135d0deb0ea1c90b8a0b883dcef249ecf47093373a71367ef9f90006c42e` |
| `cart-recheck/model-evidence.json` | `ef1c80ec2ad8f819444b4fff312d6b90d29b2d0121bc3aa668fdd750a4931098` |
| `cart-recheck/attempts.jsonl`      | `a33da5d43362a757a555bf5ba98acd7112457314dfcc2e9f313530b41c67c761` |

## Closure decision

Final regression results: **458 Python tests and 155 TypeScript tests passed**, with builds/typechecks, Ruff lint/format, ESLint and repository Prettier checks passing. Ticket 15's accepted three-run set remains attributed to its frozen runtime; it was not repeated or relabelled as a fresh full-model acceptance set for the advice release. The original failed advice exploration also remains preserved in [its report](ticket16-advice-evaluation.md). Ticket 16 is closed on this explicitly approved evidence basis, with `mvp-1` identifying the local release. Closure is a local-MVP milestone with documented limitations, not production readiness or independent-storefront compatibility.
