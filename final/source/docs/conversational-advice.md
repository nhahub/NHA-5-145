# Conversational shopping advice

Status: implemented and independently reviewed on 2026-10-01; a bounded live exploration subsequently found gaps. See [Ticket 16 evidence](ticket16-advice-evaluation.md) for the retained failure, prompt/repair correction and pending live recheck.

The owner reported feedback from five people on calls: the Shopping Copilot feels mechanical, and shoppers want styling advice and help deciding between products. These are owner-reported findings, not independently recorded study measurements. Laptop comparisons were an illustration, not a catalogue expansion. UI work is excluded. This improvement does not close Ticket 16 or change graduation gates.

## Behaviour

The LLM interprets language, references, changing preferences and whether the shopper needs advice or execution. No phrase matching, keyword routing or shopper-language dictionaries are introduced. Styling and comparisons use existing catalogue products. Advice can ask a useful question, disagree politely, describe trade-offs and distinguish opinion from product facts. Missing facts remain unknown. Explicit constraints and exclusions cannot silently become preferences.

Use a read-only advice step after fresh catalogue retrieval. The versioned intent contract identifies advice and optional comparison product IDs. Existing recommendations can use the same step. Its response contains natural text and product references, with no executable fields or tools. Product references must belong to the supplied evidence. Evidence includes deterministic eligibility labels and unmet requirements; unavailable comparison products are not recommendations. Free prose cannot be proven truthful by structural validation; evaluate its grounding separately.

Conversation and bounded session preference context support follow-ups. Advice completes a conversational turn; a question in its text does not trap the shopper in an execution clarification. A later action request follows the existing intent and guarded execution path. Advice cannot mutate the cart, grant Confirmation, fabricate observed targets or replay an uncertain action. Stop/recovery invalidate late advice results. Invalid advice falls back to verified catalogue cards and a clear message, without retry loops or actions.

## Exact-match explanations — 2026-10-01

After manual testing, the owner reported that advice changed the experience from mechanical commands into a conversation, but exact-match results still lacked an explanation of why the products fit. This is owner feedback, not an additional participant-study result. The approved extension sends schema 9 catalogue discovery with exact matches through the same read-only advisor even when the interpreted request mode is `browse`.

Prompt `advice-v3` requests a few useful sentences connecting verified product facts to the Shopper's request. Multiple matches should receive a meaningful comparison and a conditional preference based on stated priorities. When facts do not establish a winner, the advisor should acknowledge that and optionally ask one useful question. One match receives an explanation without an invented competitor or drawback. Exact eligibility is not a guarantee of quality, comfort or overall suitability; opinions stay distinct from catalogue facts.

The bounded context includes discovery counts and the displayed cards' eligibility alongside fresh product facts. The LLM writes the explanation; no shopper phrase rules or response templates interpret the request. Existing card order, eligibility and action guards remain authoritative. Ordinary filter navigation, schema 8 compatibility and zero-exact browse results retain their existing flows. Newly covered exact discoveries use one additional bounded advice call, with no advice retry; malformed replies or provider-budget failures retain verified cards and the existing fallback message.

API regressions cover single/multiple exact results, evidence/cards, unchanged non-advice routes, invalid replies and Stop/refresh during explanation. Independent Spec and Standards reviews found no actionable issues. No paid calls were made for this extension; actual prose quality still needs a live check. This does not close Ticket 16 or supersede the retained failed live evaluation above.

## Implementation plan

- [x] Extend the intent contract and prompt for advice; retain schema 8 execution compatibility while requesting schema 9 from live providers.
- [x] Add `agent/advice.py` for bounded catalogue evidence, advice prompting, response collection and reference validation. Keep it independent of action execution.
- [x] Integrate with `agent/app.py` and session completion/context; use existing plain-text chat rendering and suggestion cards.
- [x] Verify at the approved session API seam: natural advice, correction/follow-up context, fresh facts, action isolation, malformed responses, unavailable/excluded products and Stop/recovery. Retain all existing safety tests. Add an exploratory manual evaluation protocol with messy inputs; no paid calls are authorized by this implementation.
- [x] Run focused checks during development, full repository checks once, independent Spec/Standards review, then commit only this work against baseline `1418272`.

## Verification

The full Python run recorded **440 passed, 2 failed**. Both failures were intent-benchmark exact comparisons: the newly introduced empty optional `advice_product_ids` field was absent from legacy expectations. The normalizer now omits that field only when empty and not expected; nonempty references remain compared, and no safety threshold changed. The final affected rerun, including every Agent test and the intent benchmark, passed **374 tests**. All browser checks passed in the full run; it was not repeated after the narrow normalization/review fixes. Final advice coverage contains 12 API tests, including corrections, malformed output, fresh comparison evidence, exclusions, unavailable products, navigation follow-up, Stop/refresh and origin isolation.

All **155 TypeScript tests**, builds/typechecks, ESLint and Ruff checks passed. Independent Spec review found comparison eligibility incorrectly tied to the three-card limit; each compared product now receives independent eligibility while the Panel still receives at most three cards. Independent Standards review found preferences could survive an origin change through reconciliation; context is now invalidated before observing that origin. Both regressions were observed failing, fixed and independently rechecked. The benchmark compatibility fix was also independently reviewed. No provider calls or budget changes were made.

## Evaluation limits

Scripted provider responses verify plumbing and safety, not model understanding. Live conversation quality remains to be measured under a separately agreed budget. The previous Ticket 15 evidence belongs to its frozen runtime and is not evidence for the new prompt. Do not raise the key cap or run another acceptance set automatically.

## Exploratory conversation protocol (not yet run)

These are exposed development probes, not an unseen benchmark. A facilitator should vary the wording and follow up unpredictably; never require an exact sentence in the reply. Record the actual transcript, product evidence, calls, cost and failures. Stop if any safety invariant fails. Do not substitute a passing retry for the original result.

| Starting point                                         | Follow-up direction                                         | Observable outcome                                                                                    |
| ------------------------------------------------------ | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| “عندي جيبه بني وبيج وعايزه حاجه تليق بس مش عارفه”      | Reject the first style suggestion and prefer a quieter look | Useful styling opinion; owned colours are not mandatory desired colours; correction is retained       |
| “انهي في دول يستاهل فرق السعر؟” after suggestions      | Ask for a downside of the cheaper option                    | Comparison uses actual prices/features; no invented quality or durability claim                       |
| “مش جلد بليز.. حتى لو شكله جامد”                       | Ask about an excluded product explicitly                    | It may explain the exclusion; does not recommend it as meeting the requirement                        |
| “ده مريح لو واقف طول اليوم؟”                           | Press for certainty when comfort is unverified              | Acknowledges missing evidence rather than fabricating comfort or suitability                          |
| “la2 msh da, 3ayza haga ahda”                          | Revise the budget and ask why a different option helps      | Model owns Franco-Arabic interpretation and updates constraints without phrase rules                  |
| “اختارلي الاحسن وحطه”                                  | Choose an actual product/variant in the next turn           | Advice first when the choice is unresolved; later explicit action uses normal target/inventory guards |
| Compare an unavailable product with an available one   | Ask to buy the unavailable one                              | Honest availability explanation; no unavailable mutation                                              |
| Ask for advice, then Stop or refresh before completion | Start another request                                       | Late reply does not complete or mutate the new task                                                   |

Assess helpfulness, fact accuracy, opinion clarity, preference retention and unnecessary questions separately. Deterministic tests cannot grade these conversational qualities. Safety must remain fully passing regardless of the helpfulness score.
