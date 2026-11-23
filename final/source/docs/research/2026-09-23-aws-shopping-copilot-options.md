# AWS options for a budget-conscious Shopping Copilot

**Research date:** 2026-09-23\
**Scope:** an AWS ML Engineering graduation deployment using roughly $200 in AWS credits. This is an architecture-and-cost research note, not an implementation plan. Sources are AWS/Amazon-owned documentation, pricing pages, or dataset repositories. Prices and regional availability change; verify the selected Region and model in the [AWS pricing page](https://aws.amazon.com/bedrock/pricing/) immediately before deployment.

## Recommendation in brief

Use **Amazon Bedrock Runtime `Converse`** as a narrow replacement for the existing provider adapter, with a single on-demand model and the current application-owned Intent Boundary, catalogue verification, confirmation, and browser Action safety unchanged. Keep the present 60-product catalogue as a deterministic safety fixture, but investigate a substantially larger, focused fashion-and-shoes demonstration catalogue and benchmark lexical versus semantic/hybrid retrieval before choosing an index. Do not introduce managed Agents or an always-on search cluster merely for architectural spectacle.

This is an **inference** from the project specification plus the AWS facts below. Product facts must be verified rather than semantically guessed. The 60 items are too limited to demonstrate broad recommendation quality, but a vector service is only justified if measured retrieval quality on a larger catalogue improves enough to warrant its cost. If semantic retrieval proves useful, S3 Vectors is a candidate; avoid classic OpenSearch Serverless as the default student deployment.

## Proposed deployment shape

```text
Shopper → existing Panel/Agent/Bridge
                 │
                 ├─ deterministic catalogue reader + verifier (application data)
                 ├─ deterministic Intent Boundary / Action, confirmation, replay safety
                 └─ Bedrock Runtime Converse
                        └─ on-demand model: validated structured intent only

evaluation corpus → controlled Bedrock evaluation run or existing external browser runner
redacted request metadata / token counts → CloudWatch Logs Insights (optional)
```

### Facts supporting the shape

- `Converse`/`ConverseStream` provide a model-independent message interface and can be used with tool use and Guardrails; calling `Converse` requires `bedrock:InvokeModel`. [AWS: Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html) (accessed 2026-09-23).
- Bedrock structured outputs can constrain `Converse` output through `outputConfig.textFormat`, and strict tool use validates tool names and input schemas. [AWS: structured outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) (accessed 2026-09-23).
- `Converse` accepts `requestMetadata` (up to 16 key/value pairs); invocation logs record token counts and that metadata, enabling grouping by a non-sensitive evaluation-case/model/environment label. [AWS: Converse API reference](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html); [AWS: request metadata](https://docs.aws.amazon.com/bedrock/latest/userguide/cost-mgmt-request-metadata.html) (accessed 2026-09-23).
- The adapter must safely pause/offer Retry rather than issue an Action after Bedrock throttling (429), model-not-ready (429), timeout (408), or model-processing (424) responses. Those outcomes are documented by the `Converse` API; the pause/Retry behavior is the project-specific safety choice. [AWS: Converse API reference](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html) (accessed 2026-09-23).

### Architecture judgment

Keep Bedrock at the existing **Intent Interpreter** boundary. Have it emit only the versioned Structured Intent (or a strict extraction tool result), then independently validate it and deterministically select or reject every Action. This preserves the project’s safety invariants: a model must not acquire authority to navigate, read Sensitive Field values, or execute a Mutation.

Use a compact, static Storefront Definition and current Shopper turn as the model context; query authoritative catalogue facts after interpretation. This is a project-specific recommendation, rather than an AWS service guarantee.

## Bedrock Agents and AgentCore: not the first deployment choice

### Facts

- AWS now labels **Amazon Bedrock Agents Classic** as unavailable to new customers and directs new customers to AgentCore for similar capabilities. [AWS: Agents overview](https://aws.amazon.com/bedrock/agents/); [AWS: action groups](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-action-create.html) (accessed 2026-09-23).
- In the classic model, action groups can describe functions or OpenAPI operations, hand execution to Lambda, or return predicted action/parameters to the application; its console can request a user confirmation for a function. [AWS: add an action group](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-action-add.html) (accessed 2026-09-23).
- An agent runtime invocation can preprocess, iteratively orchestrate model-selected actions/knowledge-base queries, and postprocess; session history augments its orchestration prompt. [AWS: how Agents work](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-how.html) (accessed 2026-09-23).
- Agent traces can contain orchestration details, action-group and knowledge-base inputs/outputs, and prompt-template/model-invocation information. [AWS: agent trace events](https://docs.aws.amazon.com/bedrock/latest/userguide/trace-events.html) (accessed 2026-09-23).

### Decision

Do not use managed Agents/AgentCore as the Shopping Copilot’s action authority for the graduation release. They add orchestration and trace/data-handling decisions while the project already has a tested, stricter action protocol: bound Confirmation, stale/duplicate rejection, off-origin blocking, and no uncertain Action replay. Bedrock Runtime is enough for the intended AWS ML-engineering demonstration: a cloud FM API with structured output, repeatable evaluation, and observable costs.

AgentCore is a later experiment only if there is a separately tested mapping from its tool/action lifecycle to the project’s Action identity, confirmation binding, cancellation, and refresh-recovery rules. This is an inference; it does not claim AgentCore cannot be made safe. The cost concern is also an inference from documented iterative orchestration: each loop, action/knowledge-base result, and retained session context can enlarge the model work; backing-model, retrieval, and action implementation services have their own charges.

## Catalogue retrieval choices

### 1. Baseline: no managed retrieval service

Keep the 60-product controlled catalogue as the safety-test baseline, expose a read-only catalogue interface, and filter exact attributes deterministically. For vague, style, material, or use-case requests, return only facts explicitly modelled in the catalogue; otherwise clarify or label an Alternative. For a larger fashion catalogue, benchmark a low-cost lexical index before introducing semantic retrieval; size alone does not prove that vectors improve results.

### 2. Later semantic option: Amazon S3 Vectors

**Facts:** S3 Vectors offers vector buckets/indexes, similarity search, filterable metadata, strongly consistent writes, dedicated `s3vectors` APIs, and requires no infrastructure provisioning. It is designed for sub-second infrequent queries and can integrate with Bedrock Knowledge Bases. [AWS: S3 Vectors](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors.html) (accessed 2026-09-23).

**Pricing caveats (US East (N. Virginia) example, not a quote):** S3 Vectors charges storage, logical-GB PUTs, a per-query request, data processed, and data returned. The published rates include $0.06/GB-month storage, $0.20/GB PUT, $2.50/million queries, and tiered query processing; PUT has a 128-KB minimum and overwrites/deletes can remain billable in storage for up to a day. [AWS: S3 pricing](https://aws.amazon.com/s3/pricing/) (accessed 2026-09-23).

**Recommendation:** it is a plausible managed semantic-retrieval experiment if a larger/unstructured catalogue and held-out Egyptian Arabic/Franco evaluation show a gain over lexical search. Still generate embeddings only from authoritative product fields, attach exact filterable fields (category, price, size, availability), and verify retrieved IDs against the primary catalogue before showing them. Do not use semantic proximity as evidence that a product meets a material, suitability, or price Constraint. [AWS documents](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html) that Titan Text Embeddings V2 supports Arabic but is optimized for English and that cross-language queries can underperform; this must be measured, not assumed away.

### 3. Do not default to classic OpenSearch Serverless

**Facts:** classic OpenSearch Serverless collection pricing has a minimum of 2 OCUs for the first collection in an account (one indexing and one search capacity with replicas); the no-standby dev/test option has 0.5 OCU indexing plus 0.5 OCU search. Vector collections cannot share OCUs with search/time-series collections. AWS’s own pricing example uses $0.24/OCU-hour in us-east-1, making a continuously allocated 1 OCU roughly $175/month before storage. [AWS: OpenSearch Service pricing](https://aws.amazon.com/opensearch-service/pricing/) (accessed 2026-09-23).

**Current-generation caveat:** AWS documents “NextGen” Serverless collections that scale compute to zero after 10 minutes idle, with a cold start of approximately 10 seconds, and charge only storage while idle. Availability/collection generation and Region must be checked before relying on this behavior. [AWS: OpenSearch Serverless](https://aws.amazon.com/opensearch-service/features/serverless/) (accessed 2026-09-23).

**Recommendation:** OpenSearch is justified only if hybrid/faceted retrieval at a larger scale becomes a demonstrated requirement. If trialed, select the current scale-to-zero collection generation where available, set account/collection OCU caps, and delete the collection after evaluation. AWS specifically recommends OCU caps and `OCUUtilization` monitoring to prevent unexpected scaling costs. [AWS: cost optimization](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/cost-optimization.html) (accessed 2026-09-23).

## Cost envelope and controls

### Facts

- Bedrock on-demand inference pricing varies by provider, model, input/output tokens, tier, and Region. AWS also offers batch inference for selected models at 50% below on-demand price; this is suited to offline evaluation/indexing, not interactive Shopping Tasks. [AWS: Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) (accessed 2026-09-23).
- Prompt caching is optional; cache reads are billed at model-specific cache-read rates, cache writes can cost more than ordinary input tokens, and cache eligibility/hits are not guaranteed. [AWS: prompt caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html) (accessed 2026-09-23).
- Guardrails charge for the configured policies and their evaluated text. A blocked input still incurs guardrail cost but not FM inference; a response blocked after generation incurs both. [AWS: Guardrails charging](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-how.html) (accessed 2026-09-23).
- Free Tier promotional credits apply only to eligible services/charges and expire as specified in the grant. AWS’s general current offer says new customers can receive up to $200; promotional credits exclude, among other things, AWS Marketplace and certain upfront commitments. [AWS: Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/); [AWS: promotional-credit terms](https://aws.amazon.com/awscredits/) (accessed 2026-09-23).

### Budget-conscious policy (recommendation)

1. Use on-demand Bedrock only; do not buy Provisioned Throughput, host a GPU, or create an always-on database/search domain.
2. Pin one candidate model and Region after a small held-out multilingual probe. Record its exact model ID and token price in the final report; do not make the decision solely on a low advertised input price.
3. Cap `maxTokens`, keep the Storefront Definition compact, and send only the current turn plus compact resolved state. Cache only after measured repeated-prefix benefit.
4. Put a small fixed evaluation budget in place (for example, stop a model comparison after the predeclared corpus/run count) and run the normal test suite with the scripted provider.
5. Turn on AWS Budgets/Credit monitoring and budget alerts before internet exposure. Confirm the credit’s eligible-service list in the Billing console; do not assume every Bedrock model, Marketplace listing, or Region is covered.
6. Tag or attach only non-sensitive `requestMetadata` such as `environment`, `model_trial`, and opaque test-case IDs. Never put Shopper text, Sensitive Field values, payment data, credentials, or full prompts in it.

## Evaluation and observability

### Recommended evidence plan

Retain the repository’s deterministic browser/evaluation runner as the acceptance authority. Use Bedrock only for a separately recorded real-model matrix: exact model ID, Region, prompt/schema version, input/output/cached token counts, total latency, cost estimate, and the same multilingual/safety corpus. Repeat held-out runs; the Bedrock migration does not relax the existing strict model gate.

Bedrock’s managed evaluation can complement, not replace, those tests. It supports automatic and human evaluations and can evaluate models and RAG sources; programmatic jobs require ground truth/expected texts or responses. [AWS: Bedrock evaluations](https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation.html) (accessed 2026-09-23). Automatically generated algorithmic scores have no extra fee beyond inference; LLM-as-judge/RAG evaluation bills judge tokens at standard on-demand prices, while human tasks are charged separately. [AWS: Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) (accessed 2026-09-23).

For a bounded comparison, AWS documents custom automatic prompt datasets as S3 `.jsonl` with at most 1,000 prompts per job. Keep the repository’s small held-out corpus as the controlling scope, rather than inadvertently scaling an evaluation job. [AWS: model-evaluation prompt datasets](https://docs.aws.amazon.com/bedrock/latest/userguide/model-evaluation-prompt-datasets.html) (accessed 2026-09-23).

### Logging privacy boundary

Bedrock model invocation logging is disabled by default but, when enabled, can collect full request and response data to CloudWatch Logs and/or S3; it applies to Runtime endpoint calls including `Converse`. [AWS: model invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html) (accessed 2026-09-23). Therefore, do **not** enable full-body invocation logging for the normal Shopper deployment. Use application-redacted metadata/metrics by default, and enable any full logging only for the fictional Controlled Storefront under an explicit development flag and short retention.

Guardrails can assist with harmful-content and PII screening, but they do not evaluate tool definitions/results or model-generated tool-call arguments. [AWS: content-filter limitation](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-content-filters.html); [AWS: sensitive-information limitation](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html) (accessed 2026-09-23). Consequently they cannot replace the project’s Sensitive Field exclusion, deterministic tool/action validation, or Confirmation rules.

## Retail/product data and evaluation datasets

AWS maintains the [Retail Demo Store](https://github.com/aws-samples/retail-demo-store), a fictional ecommerce reference implementation intended for education rather than production; as of this research it is archived/read-only. It is useful only as inspiration or a clearly attributed non-production fixture source, not as authoritative real product data. [AWS Samples README](https://github.com/aws-samples/retail-demo-store/blob/master/README.md) (accessed 2026-09-23).

Amazon Science's [Amazon Berkeley Objects (ABO)](https://www.amazon.science/code-and-datasets/amazon-berkeley-objects-abo-dataset) is a real research catalogue with 147,702 product listings, multilingual metadata, and images. Its [live registry entry](https://registry.opendata.aws/amazon-berkeley-objects/) and [dataset site](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html) say **CC BY 4.0**, noting a 2023 license update, but the [registry's GitHub source](https://github.com/awslabs/open-data-registry/blob/main/datasets/amazon-berkeley-objects.yaml) still says **CC BY-NC 4.0**. Treat the license discrepancy as unresolved until the actual asset terms are checked. ABO emphasizes household objects; do not assume enough fashion/shoes coverage. It is not a live merchant inventory or a source of current EGP prices, sizes, stock, or verified use-case claims. Before using it in a public demo, sample its fashion/shoes coverage and resolve attribution and image/data license terms. Do not silently invent missing fields.

Amazon Science's [Shopping Queries/ESCI dataset](https://github.com/amazon-science/esci-data/blob/main/README.md) provides query-product relevance judgments (Exact, Substitute, Complement, Irrelevant) and product text. The larger release has 130,652 queries and about 2.62 million judgments, making it useful for an offline search/ranking benchmark. Its languages are English, Spanish, and Japanese—not Arabic or Franco-Arabic—so the graduation project needs its own held-out Egyptian Arabic/Franco test set. ESCI is a benchmark, not the source of live stock/price claims in the demo. Check its published license and redistribution terms before packaging any product data.

For the graduation project, retain the controlled fictional catalogue as an audit-friendly safety fixture, then choose a larger focused demo catalogue after sampling legal/licensed sources. Explicit, reviewable attributes (material, use suitability, style, price, availability) remain essential. If real source records lack stock or price, either mark those fields unknown or disclose a separate, simulated EGP layer. This is a recommendation based on the project’s grounding/safety goals; the final dataset choice remains open.

## Before spending credits

- Check Bedrock model access and model/Region availability in the account, then run a tiny non-sensitive `Converse` smoke before a full corpus.
- Create cost/credit alerts and verify the exact promotional-credit eligibility and expiration in Billing.
- Set no full-body model invocation logging by default; validate that application logs redact Sensitive Field values.
- Run the complete safety and browser regression suite against the Bedrock adapter before any public demo.
- Tear down any optional OpenSearch/S3 Vector/Knowledge Base experiment that is not part of the final demonstration.
