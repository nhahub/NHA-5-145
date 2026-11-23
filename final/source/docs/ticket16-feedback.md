# Ticket 16: reported feedback and advice follow-up

Status: closed under the owner-approved informal-study scope and release evidence basis, 2026-10-01. See [the closeout and scope adjustment](ticket16-closeout.md). The original formal-study criteria below are historical, not requirements to invent additional findings or measurements.

## Evidence collected so far

The owner reports that five people tried the application while on calls with him. He subsequently clarified that he gave no help and let them test freely until they were satisfied. Record this as owner-reported uncoached exploration, not a measured completion rate. The observations below are paraphrases of the owner's report, not verbatim participant quotations or independently recorded sessions. The original sessions have no supplied transcript, task timing, per-task completion score, recording-consent record, digital-confidence classification or explicit helped/not-helped count. Later qualitative feedback is recorded separately below. Do not infer missing measurements from the participant count. Relationships and names are unnecessary in the public study record.

| ID  | Reported finding                                                                                                                   | Evidence strength                                                                                     | Priority and response                                                                                                                                              |
| --- | ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| F01 | Conversation felt robotic; a participant wanted natural styling advice explaining why an option suits an outfit.                   | One participant's view, relayed by the owner; frequency across the other participants is unknown.     | High: introduce grounded conversational advice and relevant follow-up questions. Implemented in `16057d5`; live quality validation follows.                        |
| F02 | A participant wanted help comparing options, exploring priorities and making a decision without leaving the shopping conversation. | One participant's view, relayed by the owner; the laptop example illustrated the desired interaction. | High: explain trade-offs using verified facts in the existing catalogue. No laptop catalogue expansion. Implemented in `16057d5`; live quality validation follows. |

The owner explicitly excluded UI feedback from this improvement. Other UI comments were not supplied in detail and are not counted as separate findings. Two reported findings do not satisfy the existing ten-findings study criterion; no additional findings are invented to reach it.

## Post-advice participant feedback — 2026-10-01

The owner reported that the same five testers were with him, had seen the updated advice experience, and all expressed positive opinions. One participant explicitly described it as very useful and said they needed something like it while shopping online. This is a paraphrase relayed by the owner, not a verbatim recorded quotation. No numerical ratings were requested or supplied; qualitative feedback is valid evidence without converting it to a satisfaction score.

Record **five positive reactions** and **at least one explicit usefulness statement**. This supports the perceived value of conversational advice and responds to F01/F02; it is not five additional distinct UX findings or a replacement for technical acceptance. The exact build was not recorded. Further task and confidence details supplied by the owner are recorded below rather than inferred from the positive reactions.

The owner subsequently reported that **two participants asked to navigate to “My account,” and both attempts worked well**. This establishes reported success for those two account-navigation attempts. It does not establish that they viewed the newest order, or that all five completed the filtering and cart/checkout journeys. Per-participant identities, timings and assistance during these specific follow-up attempts were not supplied.

The owner also clarified that **all five have low confidence making purchase decisions online**, which he identified as the reason they liked the advice. Record this as purchase-decision confidence and motivation for decision support. Confidence operating shopping interfaces was not separately established; do not silently equate product-choice uncertainty with the protocol's limited-interface-confidence eligibility criterion. No numerical rating is needed for either qualitative observation.

## Bounded technical follow-up

The owner approved proceeding with documentation and a small live evaluation. This is an agent-run technical exploration with synthetic shopper messages, separate from the five people's feedback and any participant retest. It is not another Ticket 15 acceptance set or an unseen benchmark.

- Pin source `16057d5`, prompt `intent-v26`, intent schema 9 and advice prompt `advice-v1`.
- Use configured OpenRouter `google/gemini-2.5-flash` within the existing $1.00 total key cap, reset Never. A read-only check found $0.110512998 available before evaluation.
- Bound the exploration to eight shopper messages, sixteen provider calls (including interpretation repair), and $0.06 maximum reserved spend. Reserve the adapter's conservative $0.02 maximum per provider call; release the unused reservation only when attributable usage reports a valid cost. Unknown cost retains the reservation. Never increase the key cap or auto top-up.
- Exercise messy styling requests, preference/budget correction, comparison, unknown attributes, exclusions and a transition into an explicit cart action. Capture actual replies and exact cart state. Keep original failures; no repeated reruns until green.
- Use evaluation-owned local services and synthetic data. Keep raw reports under ignored `eval/reports/`; publish a redacted findings summary and provenance. Stop on an unintended mutation or other safety failure.

## Remaining Ticket 16 evidence

See [the live technical exploration](ticket16-advice-evaluation.md). It found an advice-to-navigation failure and semantic grounding weaknesses; the original failed run is retained. The resulting prompt/repair changes are verified offline only, pending a separately bounded live recheck. These technical findings are not additional participant quotations or proof that participants benefited.

Record which required tasks participants actually attempted, whether attempts were coached, explicit benefit responses and digital-confidence eligibility where known. Unknown observations stay unknown. Any additional measured sessions should follow the prepared protocol. The post-advice positive feedback above provides qualitative follow-up evidence; it cannot retroactively fill missing original task measurements.

The owner subsequently approved informal qualitative closure using the actual observations, superseding the original findings quota and formal participant/task requirements. Technical release evidence remains separate; see the closeout. CAP-03 still requires local closure and CAP-02's reviewed dataset and splits.
