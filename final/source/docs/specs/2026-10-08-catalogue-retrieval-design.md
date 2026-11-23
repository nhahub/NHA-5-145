# Catalogue retrieval for the Shopping Copilot

**Status:** owner-approved design implemented locally on 8 October 2026; new retrieval mode remains opt-in. See [verification and open qualification gates](../catalogue-retrieval-verification.md).

**Purpose:** let the Shopping Copilot investigate products and give useful advice using a small amount of relevant, current evidence. Preserve natural Egyptian Arabic, Franco-Arabic, English and mixed-language interpretation, the existing advice experience and deterministic Action safety. The owner explicitly rejects phrase-based interpretation and wants this improvement before public deployment.

This design builds on [shopper isolation](../shopper-isolation-verification.md) at commit `1a4fa1c`. It assumes the existing single Controlled Storefront and a single-host graduation demo. It does not claim support for independent retailers or production commerce. The zero-out-of-pocket [cloud constraints](../cap04-credit-only-plan.md) remain unchanged.

## Pre-migration behavior and original problem

- `store/src/catalogue.ts` contains source-code product seeds. Storefront pages, filtering and `GuardedCart` directly use exported product arrays.
- `agent/catalogue.py` downloads the complete catalogue for relevant discovery/advice requests. This is an internal HTTP transfer, not a full catalogue sent to every model call.
- `agent/llm/intent_pipeline.py` sends catalogue vocabulary, bounded known products, conversation and the observed Snapshot to the Intent Interpreter.
- `agent/advice.py` usually receives three deterministically selected suggestions; explicit comparisons can supply up to nine products. The advisor does not freely inspect other candidates.
- Discovery requires known category/property values and includes fixed ranking and styling preferences. This couples finding candidates to deciding which products deserve discussion.

Moving the arrays into a database alone does not solve these problems. The change must separate authoritative data, candidate retrieval, model interpretation and executable authority. Token savings are a measurement target, not a promised outcome: additional reasoning calls can cost more even with smaller evidence bundles.

## Options and decision

| Option                                                                  | Benefit                                                                      | Limitation                                                                  |
| ----------------------------------------------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Keep the full catalogue read and cache it                               | Small change; less repeated HTTP transfer                                    | Retains whole-catalogue coupling and fixed candidate selection              |
| **SQLite-backed product service with bounded model-directed retrieval** | Shared source of facts; focused queries; explicit search and detail requests | Requires a new read contract and migration of current array consumers       |
| Hosted vector database plus a larger autonomous agent loop              | More retrieval infrastructure                                                | Adds services/cost and does not itself verify constraints or improve advice |

Choose the second option. Begin with exact filters and lexical search; benchmark multilingual semantic retrieval behind the same boundary before selecting it for runtime. Lexical search is a baseline, not a claim that typos, Franco-Arabic or paraphrases are solved. The final retrieval choice must be documented before enabling the new path by default.

SQLite is appropriate here because the Storefront alone owns a local database with modest write concurrency. It is not a shared database file mounted across application hosts. SQLite documents this application-server pattern and its single-writer limitation. [SQLite deployment guidance](https://sqlite.org/whentouse.html).

## Ownership and modules

| Boundary                            | Owns                                                                                 | Must not own                                                                          |
| ----------------------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| Storefront product repository       | Product records, catalogue revision, parameterized queries, import/migration         | Shopper language interpretation or provider calls                                     |
| Storefront read API                 | Bounded search, facts and product details from that repository                       | Arbitrary SQL, cart writes or client-selected service destinations                    |
| Agent retrieval coordinator         | Model-directed read loop, evidence limits, cancellation and call accounting          | Phrase parsing, styling rules or mutation execution                                   |
| Intent Interpreter and advisor      | Understanding requests, search formulation, comparison, preference and clarification | Invented facts, authorization or changes to explicit requirements without the Shopper |
| Existing task and Storefront guards | Observed targets, ownership, bounds, current variants/availability and Confirmation  | Deciding what the Shopper's wording means                                             |

Use separate modules at these boundaries; do not add the retrieval loop to `sessions.py`. The HTTP app composes them. The Storefront accesses SQLite; the Python Agent accesses the configured Storefront service, not the database file. Product data is shared public catalogue data; conversation, cart, credentials and session ownership never enter a shared search index.

## Product storage and migration

1. Import the existing fictional catalogue without changing IDs, names, prices, routes, category membership, offered variants or availability. Keep a versioned seed artifact for reproducible initialization, not a second runtime data source.
2. Store product identity and bilingual text, exact Money, category/type, dates, offered size/color combinations, features and suitable uses. Preserve the existing variant semantics; do not infer stock counts or new combinations. Normalize searchable attributes and indexes behind the repository interface.
3. Represent evidence as known present, known absent or unknown where applicable. Existing omitted feature tags migrate as unknown, never as an assertion of absence. Explicit negative facts may be imported only when supported by the source data.
4. Store a schema version, a catalogue revision and product revisions. Product edits and search-index updates are atomic. Provide an explicit, transactional, repeatable import command; startup must not overwrite an existing database with seeds. A missing/unusable database produces a clear setup error, not silent fallback to arrays.
5. Migrate category pages, product pages, search/filter endpoints, cart checks, checkout and the Agent read API to the same repository. Preserve historical order snapshots; changed product records must not rewrite an already completed order.
6. Runtime database/index files belong in ignored local storage, never source control. Tests use temporary databases. Cart/session persistence and real account authentication are outside this change.

No public catalogue editing UI or unrestricted write endpoint is introduced. Versioning/import fixtures provide the price/availability change cases required for verification.

## Bounded read contract

Expose two model-facing capabilities, implemented through fixed server routes:

- `search_products`: free-text query plus typed required filters, exclusions and an optional explicit sort; returns at most ten candidate summaries per page.
- `get_product_details`: up to nine stable product IDs; returns current facts, revisions, missing IDs and supported same-origin product routes.

Category is optional for search. Generic requests must be able to search across categories without inventing a category first. Validate field names, operators, types, lengths and query complexity; use bound SQL parameters. Model input is never SQL or raw FTS query syntax. Unknown concepts remain in the semantic query or are reported as unverified requirements; they must not crash the turn or be silently dropped. Normalization may handle Unicode/case/spacing, not maintain hand-written dialect, typo, number or negation dictionaries.

Responses include catalogue revision, candidate IDs, facts sufficient for triage, requirement status, pagination/truncation and whether ranking used lexical or semantic retrieval. Exact counts are reported only for a fully evaluated predicate; never present a top-k semantic result count as the number of all matching products. Cursor state is tied to the query and revision; a changed revision requires a fresh search. Facts that support the final comparison are fetched again by ID.

For exact structured filters, apply them before limiting the candidate set. An excluded attribute known to be present cannot be an eligible recommendation. Unknown absence does not satisfy a negative requirement: it can be discussed only as uncertain, never labelled an Exact Match. Similarity and lexical scores rank evidence candidates; they do not certify product facts. Explicit price/newest sorts operate over the eligible set, not an arbitrary top-k subset.

No-match responses distinguish no verified eligible products, incomplete evidence, unsupported requirements and service failure. Alternatives retain named unmet/unknown requirements and are separate from exact results; contradictions of explicit exclusions are not automatically recommended. Searching for alternatives never changes the original requirements or authorizes a purchase.

SQLite FTS5 offers lexical matching/ranking and several tokenizers. It does not establish that this application's multilingual inputs are understood. FTS query syntax is built by the server from data, with bounded input. Verify extension availability on the pinned runtime before choosing a driver. [SQLite FTS5 documentation](https://sqlite.org/fts5.html).

## Model interaction and advice

The model remains responsible for interpreting messy language, corrections, references, quantities and negation. Introduce a versioned structured read decision using the existing provider-neutral JSON response mechanism. Decisions request search, request details, finish with an interpreted intent, or ask a clarification. Native provider tool calling is not a prerequisite. These reads are infrastructure operations, not browser Actions and not cart authority.

1. Supply conversation, current cart/visible context, known product references and compact read-capability descriptions. Do not send every product or the full catalogue vocabulary on every turn. Discover relevant attribute evidence from results; preserve the capabilities needed for existing navigation and cart operations.
2. The model chooses whether retrieval is needed. Ordinary cart quantity edits, account navigation and Stop do not automatically trigger catalogue searches. Explicit comparisons and known product references can request details directly.
3. Search returns a broader evidence pool, not three preselected recommendations. The model can inspect details or refine a search without silently relaxing the Shopper's hard requirements.
4. The advisor explains its preference using supplied facts and explicitly subjective styling judgment. The existing three-card presentation limit may remain; it applies after selection, not to the search evidence pool. New selection must not be forced by the existing neutral-palette or product-ID ranking rules.
5. Validate proposed references and factual eligibility, then use the existing task path for any requested visible Action. Retrieval success, product IDs and advice text never grant mutation authority or replace an observed DOM target/Confirmation.

Initial server limits per Shopper message: at most three model decision attempts (including the initial interpretation and any repairs), four executed read operations total, ten search summaries per page, nine detail products per operation, and one final advice completion. Search text is limited to 1,024 characters and at most twenty typed predicates; the initial contract accepts a conjunction of predicates, not arbitrary nested expressions. Alternatives use a separate read with the original requirements retained for eligibility checks. All model attempts, timeouts and failures consume the existing provider budget accounting; this design does not increase any spending cap. Hard bounds and schema validation are resource guards, not phrase matching. Each serialized read response is capped at 32 KiB of UTF-8 JSON; accumulated retrieval evidence included in a model request is capped at 48 KiB. These limits exclude separately bounded conversation/Snapshot context. Remove superseded results first and report any remaining truncation explicitly; never truncate structured price/eligibility facts into a misleading partial claim. An oversized detail record produces a structured size error. These are initial safety ceilings, not measured performance targets.

Repeated identical reads without a changed revision reuse turn-local evidence and cannot create an infinite loop. Exhaustion returns a useful partial result or one focused question; never an automatic recursive retry. Keep read evidence separate from the growing conversation history and discard superseded results. Carry stable product references across turns, then refresh facts when used.

Recheck shopper/task ownership and cancellation before every model/read operation and before accepting its completion. Stop, changed task, revoked identity or service restart prevents late results from becoming recommendations or Actions. Read failures do not replay a prior cart mutation. Retrieved product descriptions remain untrusted data, including embedded instructions.

## Freshness and safety

Refresh selected product facts before advice. Report the revision used; do not promise a quoted price remains valid indefinitely. Before add/change/checkout, the Storefront validates the current product/variant and availability from its repository. Changes that affect a Guarded Mutation's displayed terms invalidate its Confirmation; cart revision and ownership checks remain mandatory. Catalogue revision must participate in that binding where product changes alter those terms, even if cart quantities did not change.

Keep decimal Money and configured currency checks, Sensitive Field exclusion, exact-origin navigation, stale/duplicate Action rejection, ten-second Undo and uncertain-outcome recovery. Existing shopper isolation is a prerequisite throughout. No raw cookie, linking ticket, service secret or private shopper state appears in search responses, shared caches or retrieval telemetry.

## Retrieval experiment and acceptance

Create a separate versioned retrieval evaluation; do not repurpose CAP-03 intent-classifier scores as evidence of product search quality or alter its frozen data. Existing debugging cases are exposed regression data. New language-model-generated cases remain synthetic development evidence, not an unseen human test set.

Before fitting/tuning retrieval, record query groups, relevance labels, explicit requirements/exclusions and expected uncertainty. Include messy Egyptian Arabic, Franco-Arabic, English and mixed inputs; corrections, partial names, cross-category styling, several comparable products, omitted properties, no matches and adversarial product descriptions. Preserve related turns together. Add one controlled larger catalogue fixture to test boundedness and ranking beyond the small demo, without inventing factual evidence for real products.

Compare the current method, filtered lexical search and lexical/semantic candidate retrieval on the same frozen queries. Semantic indexing uses verified product text/attributes, not shopper conversation. Embedding model/version, index revision and catalogue revision must agree; a stale index cannot supply stale facts. Hydrate and validate selected IDs from the repository. Precomputed product embeddings do not eliminate query-embedding latency or host memory needs. GPU availability during development does not establish suitability for the proposed CPU cloud host.

Report candidate recall at ten, ranked relevance, named-product recovery, requirement/exclusion violations, no-match/unknown handling, per-language failures, p50/p95 latency, context size, total model calls/tokens and measured cost where available. Publish failures, not only averages. Do not choose runtime semantic retrieval merely because it is more sophisticated. Select it only if it improves candidate retrieval without safety regressions and fits the measured deployment resource envelope; otherwise document the baseline's limits and remaining retrieval work.

Mandatory acceptance before default activation:

- Migrated seed data, visible pages, product identities, exact prices and offered variants match the current catalogue.
- Every declared safety regression passes, including misleading product text, exclusions, stale price/availability, ownership changes, Stop and duplicate delivery.
- Injected deterministic clients prove the complete search/detail/refine/advice protocol and all call/size limits without provider spending.
- The search experiment, backend selection and limitations are recorded. Ordinary task paths retain behavior and avoid unnecessary read loops.
- A bounded actual-model evaluation demonstrates natural query formulation and advice on the recorded cases before claiming the new path works with the deployed model. Its budget must fit the owner's existing explicit allowance; if unavailable, leave live qualification open and do not substitute scripted success for it.
- Run focused checks during implementation, then relevant repository format/lint/build/typechecks and full regression tests. Review the service, language/safety and migration boundaries before integration.

## Delivery and exclusions

The implementation plan should sequence repository migration, bounded read API, retrieval comparison, then model-directed integration and end-to-end verification. Each slice must preserve an operational regression-tested app. Remove the normal Agent whole-catalogue fetch when its consumers have migrated; a seed export needed by offline fixtures is not a runtime fallback. Do not operate two competing catalogue sources.

No hosted vector service, AWS resource, new paid subscription, provider-budget increase, retailer integration, real inventory reservation, account system, cart persistence or frontend redesign is included. SQLite driver/runtime compatibility and the semantic backend are implementation decisions backed by checks, not new product features. Public HTTPS, global inference allowances and abuse controls remain separate deployment gates.

The next step is owner review of the implementation plan and confirmation of execution method. This document is not evidence that retrieval is implemented, benchmarked or qualified.
