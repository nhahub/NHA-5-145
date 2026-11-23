# Ticket 16: five-person uncoached study protocol

**Historical protocol:** on 2026-10-01 the owner approved Ticket 16 as an informal qualitative study based on actual observations. The formal participant, task, findings-count and manual-comparison closure criteria below are superseded by [the approved scope adjustment](ticket16-closeout.md). Preserve this protocol as the original design; do not claim it was executed or passed. Consent remains necessary for any future recording or reuse of participant data.

**Protocol version:** 0.1, prepared 2026-09-29.

**State:** the owner subsequently reported five informal testers on calls and two advice-related findings. See [the evidence ledger](ticket16-feedback.md); formal task measurements and protocol adherence remain unverified.

**Execution gate:** Ticket 15 accepted, a stable build identified, facilitator assigned, privacy/consent arrangements confirmed, and a bounded model-call budget authorized. Preparing this protocol does not waive those prerequisites.

## Purpose and sample

Observe whether five people can complete the three headline Shopping Tasks without coaching, whether the Copilot helps them, and where they hesitate or lose trust. At least two participants should self-report limited confidence using online shopping interfaces. Recruit outside the implementation team; record relevant language/script preferences and shopping confidence without collecting unnecessary demographics. Five participants support exploratory usability findings, not population-level effectiveness claims.

Use anonymous identifiers P01–P05 in project evidence. A team-designated facilitator holds scheduling/consent information separately in restricted initiative storage. Participation is voluntary and may stop at any time. Obtain explicit recording consent before screen or audio capture; permit participation with observation notes only. Ask separately before reusing an anonymized quotation or input example. Do not reuse study inputs as unseen benchmark data after the team has analyzed them.

## Session preparation

- Record source revision, model/provider and prompt/schema version, browser version, viewport, language and starting Storefront state in the session sheet.
- Use text input for the measured study. Voice availability is optional context, not a requirement; current OpenRouter speech allowance is insufficient and no cap increase is authorized.
- Check service health and run one facilitator-only rehearsal with scripted execution or an explicitly budgeted live call. Keep rehearsal results outside participant outcomes. Do not tune prompts between participants in one cohort; if a fix is necessary, version the cohort and preserve both sets of results.
- Use fictional accounts and products only. Supply the fixed test login `study-shopper@example.test` / `study-fictional-password` on a separate card. These values are test data, never a real account. The Shopper types login details directly into the Storefront, never into chat.
- Reset the Controlled Storefront and use a fresh Copilot session before each task/mode. Reset affects shared local state: use an isolated study instance or an agreed exclusive study session, never an occupied demo. Rehearse reset and cart fixtures before recruiting.
- Before each measured session, verify catalogue availability/options and newest order against the pinned fixtures. Current sources are `store/src/catalogue.ts` and `store/src/views.ts`; record actual expected results in the facilitator sheet. Fixture drift pauses the study for correction rather than silently changing success criteria.
- Prepare the cart for task 2 with only `shoe-09` (Nile Walk / ممشى النيل), size 43, blue, quantity 1, no active Undo. Current fixture price is 1850 EGP. Keep fixture setup invisible to the participant and identical across modes.

## Neutral introduction

Read in the participant's preferred language:

> We are testing the application, not you. This shop and its account/order data are fictional; no purchase or payment will happen. Please use your own words and work as you normally would. You can stop at any time. I cannot tell you where to click or what to type during a task. If you get stuck, say so. We will ask about your experience after each task.

Explain only the mode: in Copilot mode use the conversation panel, answer its questions and handle requested login yourself; in manual mode use Storefront controls without the Copilot. Identify the input area before timing, but provide no example shopping command or demonstration of the measured tasks. The participant may stop, correct themselves, or use visible controls; record any manual fallback within Copilot mode separately.

## Task cards and outcome checks

Present goals, not prompts to copy. Read/translate the same meaning naturally if needed; log the language used. All three tasks are required in Copilot mode for every participant.

| Task                          | Participant card                                                                                                                                                                | Starting state                                    | Facilitator's observable success check                                                                                                                                              |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1: Discovery                  | Find available running shoes in size 42 costing at most 2000 EGP. Show the results and identify one suitable choice.                                                            | Home, fresh session, empty cart                   | Category/type, size and inclusive budget are applied or verified against actual results; chosen product is available and meets each requirement. A narration alone is insufficient. |
| 2: Cart and checkout guidance | Your cart contains one blue Nile Walk in size 43. Change it to two, then find where you would continue to payment. Stop before entering payment details or submitting an order. | Home; exact one-line cart fixture described above | Same product/variant quantity is exactly 2; participant identifies the checkout control or reaches the fictional checkout page. No payment values entered and no order submitted.   |
| 3: Newest order               | Find the newest order in the supplied demonstration account and tell us its number. Use the supplied fictional login card if needed.                                            | Home, logged out, fresh session                   | Shopper handles authentication; order 1003 is identified on the orders page (and Spotlight recorded if used). Copilot never reads/types credentials.                                |

Optional observation after the timed cart task: ask whether the participant noticed a way to undo their change. Do not retroactively score that answer as an uncoached Undo success. A timed ten-second Undo exercise is outside the three headline outcomes unless separately specified before recruitment.

## Manual-shopping comparison

Use a small within-participant comparison without changing Ticket 16's core sample or claiming statistical significance. Everyone attempts the three headline tasks in both modes if willing. P01/P03/P05 use Copilot first; P02/P04 use manual first. The 3/2 split is approximately balanced, not perfect counterbalancing. Keep the same device, tasks and fixture resets for comparability; disclose the learning effect from repeated tasks and show results by mode order.

Rotate task order: P01/P04 = 1,2,3; P02/P05 = 2,3,1; P03 = 3,1,2. Use that order in both modes. Target 35–45 minutes with a break; allow five minutes per task. A participant may decline the comparison without losing their recorded core study outcomes; report missing comparisons rather than filling them in. No coaching is added to make either mode look better.

## Timing, assistance and stopping rules

Start timing when the participant finishes reading the card and says they are ready. Stop at verified completion, voluntary abandonment, five-minute timeout, or a safety/technical stop. Record elapsed wall time, including model waiting, with any infrastructure outage separately identified. An unavailable provider is a technical failure, not an interpretation error or participant failure.

If asked for help, the facilitator may repeat the goal or say, "Please do what you would normally try." Any hint about wording, navigation, or controls makes the outcome assisted; record the exact intervention and time. Never change an assisted attempt into an uncoached pass. Stop immediately on unintended consequential behaviour, real personal-data entry, participant distress, or a safety invariant failure. Preserve only privacy-safe evidence and suspend further sessions until the issue is assessed.

Record both task success and completion method: Copilot-only interactions plus expected authentication/confirmation, Copilot with manual fallback, manual mode, or facilitator-assisted. Report the distinctions rather than crediting a manual rescue as autonomous Copilot success.

## Observation and interview sheets

For every attempt record:

| Participant | Mode and order | Task | Start-state verified | Outcome: unassisted / assisted / failed / timeout / technical / declined | Completion method | Elapsed seconds | Errors and retries | Hesitations | Help/intervention | Safety concern | Evidence reference |
| ----------- | -------------- | ---- | -------------------- | ------------------------------------------------------------------------ | ----------------- | --------------- | ------------------ | ----------- | ----------------- | -------------- | ------------------ |

A hesitation is a visible pause or uncertainty; note its context and approximate duration without inventing a universal threshold. Ask immediately after each task: "How easy or difficult was this task, from 1 (very difficult) to 5 (very easy)?" Then ask what caused difficulty. Avoid requiring continuous think-aloud during timing; it can distort the manual comparison.

After both modes ask:

1. Did the Copilot help you with these tasks: yes, partly, or no? Why?
2. What did you think it was doing when you waited or saw an Action?
3. Was there a moment you felt unsure about what would happen?
4. When would you prefer shopping manually?
5. What single change would help you most?

For the local gate, count only explicit "yes" as the protocol's conservative helped response; report "partly" separately. At least three of five must report help. Do not pressure participants to meet that threshold.

## Analysis and completion

Report per-task counts out of five, assisted/fallback/technical outcomes, actual elapsed times and medians, mode order, missing observations and participant comments. With this sample, avoid significance claims or universal speed-up percentages. Maintain a findings table with evidence IDs, observed impact, frequency, proposed in-scope fix and verification.

Ticket 16 requires at least ten concrete prioritized UX findings. Do not fabricate findings to fill a quota; if fewer are observed, report that criterion as unmet and discuss further observation. Address the highest-impact in-scope failures, add regression coverage for behaviour changes, and rerun applicable evaluation gates within separately authorized budgets. Record post-fix evidence separately from the initial cohort.

Publish aggregate findings and limitations in `RESULTS.md` when the gate actually closes. Raw notes/recordings stay in restricted initiative storage; the study lead records its location and access list before collection. Proposed retention is through assessment plus 30 days, then deletion unless initiative policy requires another period; confirm that policy before recruitment. This protocol is preparation, not study completion or local-MVP acceptance.
