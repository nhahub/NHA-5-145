# Catalogue retrieval implementation and qualification

Date: 8 October 2026. Branch: `feature/shopper-isolation`.
Implementation base: `12d36f7`, after shopper-isolation work. No provider calls,
cloud resources, budget changes, push or deployment were made in this slice.

## What changed

The Storefront owns an explicitly initialized SQLite product repository. Product
pages, category filtering, cart checks, checkout and the private read service use
that same database. Opening a missing database fails; startup never reseeds it.
Each synchronous request holds one SQLite read transaction from validation through
order serialization. All 60 fictional seed records, IDs, routes, Money strings and variant choices are
preserved. Submitted orders retain their original unit prices and names.

`/__internal/catalogue/search` and `/details` require the existing private service
credential. Queries have typed, parameterized predicates, revision-bound cursors
and conditional reads. Feature/use facts distinguish present, absent and unknown;
missing data never establishes an exclusion. Current catalogue changes invalidate
old checkout terms, and withdrawn variants reject quantity changes while removal
and the original Undo deadline remain available.

With `CATALOGUE_RETRIEVAL_ENABLED=1`, the model chooses reads, refinement and up to
three products. It sees bounded current evidence, conversation and the shopper's
Snapshot/cart controls. There is no phrase dictionary, negation parser or typo
mapping in this new path. Original requirements survive refinement. Fresh selected
details feed the advisor; known forbidden products cannot become recommendation
cards. Unknown exclusions remain explicitly unverified alternatives. A null exact
count means the total is unknown; a similarity result is not an exact match count.

Limits per shopper message: three decision attempts including schema repairs,
four executed reads (one reserved for final refresh), and one advice completion.
Conditional HTTP revalidation counts as a read. New-path requests disable hidden
Groq/Nvidia retries; Retry retains its remaining budget. Exhaustion ends with a
question rather than an unusable Retry. Stop, changed Snapshot or revoked shopper
authority discards late results. Comparison identities persist in bounded session
memory but never authorize an Action or select a cart variant.

## Evidence and honest limits

- The new browser scenario uses real SQLite, private HTTP reads, Agent sessions,
  Bridge Actions and two independent browser contexts. A scripted model selects
  the ninth candidate, advises with an unknown material exclusion, opens/adds it,
  then changes only its quantity in a two-line cart. The other shopper stays empty.
- Focused regression coverage includes price/availability/variant changes,
  immutable order facts, bounded/conditional reads, invalid cursors/indexes,
  literal FTS syntax, requirement preservation, unavailable/forbidden cards,
  shared provider budgets, comparison references and cancellation.
- Independent Spec/Standards reviews found and then verified fixes for exclusions,
  withdrawn variants, hidden provider retries, lost comparison identities and
  unusable exhaustion Retry. Neither reviewer reports a remaining actionable issue.
- A clean full Python rerun passed **531 tests** in 595 seconds. Three subsequently
  added regressions passed in focused runs, giving **534 distinct passing tests**;
  this is not a claim that one invocation ran all 534. The final focused Python
  check passed 61 tests across retrieval, advice and historical model comparison.
- Recursive TypeScript tests passed 179 tests; later focused Storefront checks cover
  the three added regressions, giving **182 distinct passing tests** (59 Storefront,
  85 Bridge, 38 Panel). Recursive builds, test-inclusive typechecks, Prettier, ESLint,
  Ruff check/format and diff whitespace checks pass.
- An earlier interrupted run left owned test processes on the evaluation ports;
  those were cleared before the clean full rerun. Its port-conflict failures are
  not presented as application failures or omitted from the verification history.
- Scripted models test execution and boundaries. They are **not** evidence of
  natural-language interpretation or prose fidelity by the paid model.

### Offline retrieval comparison

The frozen 40-query set has ten queries per language group. All are synthetic,
exposed development inputs with provisional, non-exhaustive target labels. No
CAP-02/03 split, label or result was changed. The historical catalogue source has
an exact hash-verified archive in `eval/frozen-sources/` so the old pilot release
can still be loaded after the runtime migration.

| Query group     | Lexical target recall@10 | Hybrid target recall@10 |
| --------------- | -----------------------: | ----------------------: |
| Egyptian Arabic |                       0% |                     40% |
| Franco-Arabic   |                      80% |                    100% |
| English         |                     100% |                    100% |
| Mixed           |                      90% |                    100% |
| Overall         |                    67.5% |                     85% |

Hybrid uses pinned multilingual MiniLM embeddings and reciprocal-rank fusion;
SQL filtering precedes ranking. Missing/stale vectors fail explicitly. Lexical
mode imports no embedding packages and downloads no weights. The historical
full-read baseline contains all 60 products (100% candidate coverage); that is
not a model-accuracy or three-card-selection comparison.

The 1,000-row CPU fixture repeats seed facts with unique IDs and cached vectors.
Measured warm ranking p95 was about 3 ms lexical / 39 ms hybrid, with Node RSS
about 243 MiB. These numbers exclude query encoding, HTTP and the other services.
They do **not** establish a one-second end-to-end p95 or a 2 GiB host fit. Arabic
raw-query recall remains weak; LLM reformulation has not yet been measured.
See `eval/evidence/catalogue-retrieval-v1.json` for per-query observations.

## Activation and remaining work

The SQLite migration is active in this checkout. The existing advice path remains
usable through a database-backed compatibility endpoint. The new model-directed
path remains **opt-in**; default activation and deployment are unqualified.

Before promoting it:

1. Run a separately authorized, bounded actual-model evaluation of messy queries
   and grouped follow-ups, including exclusions, comparisons, corrections and cart
   actions. Record evidence grounding, calls/tokens/cost and latency. No prior
   capped acceptance allowance is assumed to fund this experiment.
2. Measure end-to-end warm retrieval and whole-stack memory on the intended CPU
   host, including the encoder if hybrid is selected, retaining 512 MiB headroom.
3. Decide whether lexical plus model reformulation or hybrid meets the gates.
   Neither raw retrieval metrics nor schema-valid prose justify claiming success.
4. Complete remaining public deployment controls from the shopper-isolation and
   CAP-04/05 plans. This change creates no cloud deployment.

## Reproduction

Normal local startup first requires the existing identity initialization and:

```sh
pnpm --filter @shopping-copilot/store exec tsx scripts/catalogue-import.ts
```

Then start the Storefront, Agent and Panel as documented in the README. For the
new path, set `CATALOGUE_RETRIEVAL_ENABLED=1` only in the local environment and keep
`CATALOGUE_RANKING=lexical` initially. Live use consumes the configured provider's
allowance; automated tests use injected scripted clients.

To reproduce the offline comparison without a provider:

```sh
pnpm --filter @shopping-copilot/store exec tsx scripts/catalogue-import.ts --database ../work/catalogue-retrieval/evaluation.sqlite
pnpm --filter @shopping-copilot/store exec tsx scripts/catalogue-import.ts --database ../work/catalogue-retrieval/evaluation.sqlite --export ../work/catalogue-retrieval/products.json
python -m eval.catalogue_retrieval --cache <existing-pinned-model-cache>
```

The encoder loads locally cached safetensors only. The comparison writes ignored
indexes and load fixtures under `work/catalogue-retrieval/`; it never installs
weights, publishes a dataset or calls a model provider. Its evidence file can be
regenerated locally; timings vary by machine.

For optional hybrid runtime, explicitly export a current catalogue, encode its
products with the pinned model and load the resulting revision-bound index using
`catalogue-import.ts --database <db> --index <index.json>`. Rebuild after imports;
stale indexes are rejected. Set `CATALOGUE_RANKING=hybrid` in both the Storefront
and Agent process environments (the Node service does not load the Agent `.env`).
No background embedding download or automatic reseed.
