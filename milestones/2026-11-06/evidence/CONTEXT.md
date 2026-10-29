# Shopping Copilot

The Shopping Copilot helps a shopper complete shopping tasks on an ecommerce storefront through natural language while keeping consequential actions visible and under the shopper's control.

## Language

**Shopping Copilot**:
The assistant that interprets a Shopper's request and helps carry it out on a Storefront.
_Avoid_: Bot, generic agent

**Shopper**:
The person asking the Shopping Copilot for help and retaining control over consequential choices.
_Avoid_: User, customer, operator

**Storefront**:
The ecommerce experience in which the Shopper browses products, manages a cart, checks out, and reviews orders.
_Avoid_: Website, target site, shop UI

**Storefront Definition**:
The authoritative description of a Storefront's known capabilities and constraints, including its vocabulary and configured currency.
_Avoid_: Site map, agent configuration, hardcoded store knowledge

**Controlled Storefront**:
The Storefront owned by this project and used to develop and evaluate the local MVP under reproducible conditions.
_Avoid_: Fake store, fixture site, our store

**Shopping Task**:
A bounded goal expressed by the Shopper that the Shopping Copilot either completes, safely hands back, or declines as off-topic.
_Avoid_: Job, workflow, prompt

**Constraint**:
A Shopper-supplied condition that narrows acceptable results, such as category, use, price, or size.
_Avoid_: Filter when referring to the Shopper's intent

**Catalogue Fact**:
An explicit Storefront assertion about a product's identity, availability, property, or suitable use. An absent fact is unverified, not a fact the Shopping Copilot may infer from a product name.
_Avoid_: Model guess, implicit product knowledge

**Exact Match**:
An available catalogue product for which every explicit non-negotiable Shopper requirement is verified by authoritative product facts.
_Avoid_: Search hit, plausible product

**Alternative**:
An available catalogue product offered despite one or more named unmet or unverified Shopper requirements, never presented as an Exact Match.
_Avoid_: Match, silent fallback

**Styling Suggestion**:
An available catalogue product proposed for an open-ended coordination goal. Its product details and explicit requirements are verified; its colour-coordination advice is a styling opinion, not a product fact or a guarantee.
_Avoid_: Personalized recommendation, model guess

**Owned Outfit Context**:
The garments and footwear a Shopper already has and wants to coordinate with. Their properties describe the owned items, not requirements for the product being sought.
_Avoid_: Desired product filters, shopping history

**Styling Preference**:
A soft coordination idea, such as a neutral or complementary colour, used to rank otherwise acceptable products. It cannot silently replace or relax a Shopper's explicit Constraint.
_Avoid_: Mandatory filter, verified suitability

**Snapshot**:
A semantic description of the current Storefront state that contains only the information needed to understand available interactions.
_Avoid_: DOM dump, page scrape

**Action**:
One proposed interaction with the Storefront in service of the current Shopping Task.
_Avoid_: Tool call, command, operation

**Spotlight**:
A visual cue that identifies a relevant Storefront element while leaving the next choice to the Shopper.
_Avoid_: Highlight, tooltip

**Sensitive Field**:
A field whose value the Shopping Copilot must neither read nor enter, including credentials, payment-card data, and one-time codes.
_Avoid_: Secret input, protected textbox

**Mutation**:
An Action that changes shopping state or commits a consequential choice.
_Avoid_: Write action, side effect

**Reversible Mutation**:
A cart Mutation whose precise prior state can be restored through Undo without further Shopper input.
_Avoid_: Safe action, unimportant change

**Guarded Mutation**:
A destructive or terminal Mutation that requires Confirmation before it may execute.
_Avoid_: Dangerous click, high-risk tool call

**Confirmation**:
An explicit Shopper decision that authorizes one specific Guarded Mutation within the current Shopping Task.
_Avoid_: Approval, consent prompt

**Undo**:
A time-limited opportunity to restore the exact shopping state that existed before a Reversible Mutation.
_Avoid_: Rollback, cancel

**Money**:
An exact decimal amount paired with the ISO currency configured by the Storefront Definition.
_Avoid_: Price number, floating-point amount

**Intent Interpreter**:
The Agent-side model that interprets the Shopper's language using current Storefront observations and task context, including references, quantities, exclusions, and clarification. Its proposed operation and observed target do not authorize execution or replace Confirmation.
_Avoid_: Brain, autonomous planner, action model

**Structured Intent**:
The versioned result of Intent interpretation: language, dialect, intent kind, canonical Constraints including exclusions, observed target, browsing or recommendation goal, Owned Outfit Context, and clarification state.
_Avoid_: Raw model response, free-form plan

**Intent Boundary**:
The runtime validation point between model interpretation and Shopping Task execution. It checks supported capabilities, observed targets, bounds, freshness, and required Confirmation; it does not reinterpret Shopper wording or require particular phrases.
_Avoid_: Model safety, implicit guardrail

## Project references

- [PROJECT_CHECKPOINT.md](PROJECT_CHECKPOINT.md) records the current execution frontier, verified evidence, and the next safe continuation point.
