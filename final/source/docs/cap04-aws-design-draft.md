# CAP-04: AWS design decision brief

**11 October revision:** This document is historical. Use the [current cloud-readiness design](specs/2026-10-11-cap04-cloud-readiness-design.md), which supersedes the supervised single-shopper/shared-cart and coordinated-reset assumptions below. The public ingress topology remains a candidate pending browser, account and cost evidence.

Prepared: **6 October 2026**. Status: **recommendation for review; CAP-04 remains open**.

**7 October update:** the owner requires credit-only operation with zero out-of-pocket payment, has created a Free-plan account ($100 credit and a 7 April 2027 plan end date shown in their screenshot), has no domain and wants a public link for independent testers. Read the [current constraints and 60-day estimate](cap04-credit-only-plan.md) and [pricing research](cap04-pricing-research.md) first. The supervised admission/domain proposal below is retained as an earlier option, not the selected design; public isolation and domain-free HTTPS remain unresolved.

Recommend one small Linux EC2 host for a scheduled, supervised demonstration of the existing Controlled Storefront, with two HTTPS origins and a narrowly permitted Bedrock adapter. This is a proposal, not an approved architecture or deployment instruction. The actual AWS account, Region, model, remaining credits, operating ceiling, audience and access arrangement are pending. Choosing an option does not authorize account inspection, subscriptions, paid inference, resource creation or deployment.

This preparation follows the [graduation requirements](cap01-requirements.md#graduation-ml-and-deployment-requirements), current checkpoint and [system design](system-analysis-design.md). The owner-approved local closure is recorded separately; its evidence does not qualify AWS. CAP-05 still requires the dataset/model/design prerequisites and strict model qualification; CAP-06 deploys only after those gates, and CAP-07 verifies the deployed result. This brief changes no runtime, model configuration, spending cap or roadmap gate.

## Recommended option: one supervised EC2 host

Use one EC2 Linux instance, one encrypted gp3 volume and one public IPv4 address in an approved Region. A reverse proxy serves the built Panel, forwards Storefront requests to its single Node process, and forwards Agent requests to its single Python worker. Build artifacts before deployment; do not expose a development server or reload mode. Start with a **candidate** `t3.small` (2 vCPU, 2 GB RAM); measure memory and latency before accepting that size. Use standard CPU-credit mode and test throttling under the expected workload rather than silently incurring Unlimited-mode surplus charges. AWS documents those additional charges on its [EC2 pricing page](https://aws.amazon.com/ec2/pricing/on-demand/).

```text
Authorized supervised Chromium browser
  | HTTPS, client certificate, network allowlist
  v
One EC2 host: reverse proxy / admission boundary
  |-- panel.<owner-domain>      -> built Panel assets
  |-- panel.<owner-domain>/api/ -> one Agent worker -> Bedrock Converse
  |-- store.<owner-domain>      -> one Storefront process + Bridge
  |                               ^
  |                     Agent's private catalogue requests
  `-- encrypted disk: release/config, bounded logs, spending ledger

Browser: Panel <-- exact-origin postMessage --> Storefront iframe
         Agent events return over same-origin /api/... SSE
```

These are illustrative hostnames, not registered domains. The two HTTPS subdomains preserve the Panel/Storefront origin boundary while the Agent API is same-origin with the Panel. Loopback-only application ports prevent bypassing the proxy. Use one network path to regional Bedrock over HTTPS; no NAT gateway, load balancer, database, Redis, CDN, EKS, SageMaker endpoint or Bedrock Agent is proposed for this small demo. IAM, AWS Budgets and bounded operational monitoring support the host; each additional service must have a specific need and cost.

The trade-off is explicit downtime during updates, owner-managed OS/proxy maintenance and no high availability. That is acceptable only if the owner approves the scheduled demonstration audience and reset policy. It is not production readiness.

### Access and browser boundaries

The proposed access gate is a dedicated, short-lived client certificate accepted by the reverse proxy on **both** hostnames, plus a security-group source-IP allowlist. The owner admits one supervised browser profile and one active Shopping Task session at a time; disconnect and reset before handing it to another participant. Client-certificate validation is a supported [NGINX capability](https://nginx.org/en/docs/http/ngx_http_ssl_module.html#ssl_verify_client). Certificate issuance, secure delivery/revocation, supported Chromium behavior, domain ownership and server TLS issuance/renewal remain decisions to validate. If this admission method is unsuitable for the actual audience, revise the design before exposure; do not fall back to the fictional Storefront login.

This gate authenticates the demo client, not fictional shopping identities. A session ID, tab lease or `fictional_session` cookie is not production authentication. Cloud work must enforce the single admitted session and deny unauthorized session creation, reads, SSE, answers and ActionResults. Source-IP filtering alone cannot distinguish people sharing a network. Broad public access or concurrent independent participants would require a different reviewed authorization/state design, or an independently isolated full instance per participant.

Configure exact public origins in the Panel, Bridge, Agent and Storefront Definition. The current [Panel entry point](../panel/src/main.ts) and [Agent application](../agent/app.py) contain localhost assumptions, so DNS changes alone will not deploy this runtime. Keep browser-facing Storefront URLs separate from the Agent's private catalogue base URL. Preserve URL validation against the configured public Storefront; do not weaken it to arbitrary hosts.

The Panel allows only the intended Storefront in `frame-src`; the Storefront allows only the Panel in `frame-ancestors`, which controls who may embed it ([MDN reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors)). Preserve exact `postMessage` origin **and source-window** checks. Do not install a conflicting `X-Frame-Options: SAMEORIGIN` policy on the cross-origin Storefront frame. Require HTTPS, host-scoped cookies and appropriate Secure/SameSite settings. Same-site subdomains still have distinct origins. Check Origin/CSRF protections for mutations and reject unexpected hosts; CORS is not authentication. Exclude development/reset/test routes from public routing and production startup.

For SSE, disable proxy buffering and caching on the event route, flush events promptly, and set idle timeouts above a tested heartbeat interval; NGINX documents [response buffering and timeout controls](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering). Preserve event IDs/cursors and refresh reconciliation. Test long idle periods, disconnect/reconnect, Stop and duplicate event delivery through actual HTTPS. Browser SSE does **not** require Bedrock token streaming: initial qualification can use non-streaming `Converse` behind the existing event channel.

## Shared cart and restart contract

The [implemented state model](system-analysis-design.md#8-logical-data-model-and-lifetime) has one in-memory GuardedCart per Storefront instance and in-memory Agent sessions. Separate Agent sessions do not isolate carts. The recommendation deliberately supports **one admitted session per whole application instance**. One Agent worker and one Storefront process are required; horizontal replicas, overlapping releases and additional Python workers cannot be enabled without revisiting state ownership.

Proposed reset contract for owner approval:

- A browser refresh reconciles the existing session while its processes remain alive. It never authorizes automatic replay of an Action with an uncertain outcome.
- A Storefront or Agent crash closes admission. Restart both stateful processes as a coordinated unit; discard sessions, cart, fictional orders, Confirmation and Undo state, invalidate old browser authority, and reopen only after health checks. This coordination and reset detection are implementation work, not an existing guarantee.
- The Panel visibly reports that the demo was reset and requires a fresh session. A surviving browser may not submit cached Actions, results or Confirmation into the new instance. Test Agent-only and Storefront-only failure as well as full-host restart.
- Participant turnover revokes admission, closes the old browser session, resets the full stack and admits the next participant. No partial cart reset through an exposed development endpoint.
- The spending ledger persists separately on encrypted disk across resets and rollbacks. If its integrity or total is uncertain, inference remains disabled until reconciled; restoring an older application artifact must not restore an older allowance.

No durable shopping history or cross-restart task recovery is promised. Persistence would require a justified schema for ownership, expiry and mutation authority, not merely mounting a volume. These restrictions protect the four existing safety invariants: off-origin rejection, Sensitive Field exclusion, bound Confirmation, and stale/duplicate Action rejection.

## Bedrock selection and permissions

The [provider factory](../agent/llm/factory.py) does not yet provide a Bedrock adapter. CAP-05 should add the narrow provider implementation behind the existing contract, preserving Structured Intent validation, bounded repair and advice separation. Do not use a model migration to change Action authority or accept unvalidated prose.

Select the exact model/version only after checking its current [model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.html), [regional availability](https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html), Converse capabilities and token prices. Arabic/Franco-Arabic quality and required schema behavior need project qualification; a supported API is not evidence of task accuracy. Prefer regional on-demand inference if the selected qualified model supports it. Do not select a global or geographic inference profile implicitly.

AWS's [Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html) accepts a model or inference-profile identifier, returns usage data and requires `bedrock:InvokeModel`. Grant only the selected resource permissions to the runtime role. Grant `bedrock:InvokeModelWithResponseStream` only if the adapter actually uses streaming; a kill switch must cover both invocation paths. Bound input/output tokens, retries and concurrency, and account for interpreter, advice and repair calls.

Use an [EC2 instance role](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html) with temporary credentials, not a static AWS key embedded in images, source, browser bundles or environment examples. Require IMDSv2 and review metadata reachability for the chosen process/container layout ([EC2 metadata documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-metadata.html)). Restrict metadata access to the Agent where practicable; processes sharing a host are not a strong security isolation boundary.

AWS currently documents [automatic model access prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html), including Marketplace permissions/payment arrangements for applicable third-party models and Anthropic first-use requirements. A separate authorized setup identity should perform any required enablement; the runtime role does not need ongoing subscription authority once access is enabled. First invocation can initiate subscription and accept provider terms, so it is not a harmless access probe. No account or entitlement was inspected here.

If a chosen model requires cross-Region inference, record its source and all permitted destination Regions, processing/residency implications and exact profile ARN. [Geographic profile permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/geographic-cross-region-inference.html) include the profile and relevant foundation-model resources; organization policies can also block routing. Confirm that arrangement explicitly rather than granting every model/Region wildcard.

## Cost model: illustration, not a spending authorization

All figures are USD, exclude credits and assume no Free Tier entitlement. Published example prices below are reference inputs, not a quote for an unselected account/Region. Reprice the selected Linux instance, storage, model, DNS/TLS and network options before approving an operating ceiling.

Illustrative demonstration window: **14 calendar days**, one instance running **120 hours**, a public IPv4 retained for **336 hours**, and **20 GB gp3** retained for all 14 days. Estimate 10 supervised sessions × 20 turns × two model calls per turn × a twofold retry/rehearsal allowance = **800 total calls**. At an assumed average of 4,000 input and 600 output tokens per call, that is **3.2 million input + 0.48 million output tokens**. Those averages are planning assumptions, not measurements or hard limits. CAP-05 qualification/comparison calls need a separate allowance and are excluded from this demonstration example. Optional speech-provider usage is also excluded and must stay disabled unless separately costed and authorized.

| Component                | Reference input and calculation                                                                                                                                                                                                                             | Illustrative cost |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| EC2 compute              | 120 × $0.0208; AWS's [T3 example](https://docs.aws.amazon.com/prescriptive-guidance/latest/optimize-costs-microsoft-workloads/right-size-selection.html) lists this hourly `t3.small` price in `us-east-1`; this is not the selected Region or final quote. | $2.50             |
| Public IPv4              | 336 × $0.005; [VPC pricing](https://aws.amazon.com/vpc/pricing/) charges in-use and idle public IPv4.                                                                                                                                                       | $1.68             |
| gp3 volume               | 20 × $0.08 × 14/30, using the [EBS pricing example's](https://aws.amazon.com/ebs/pricing/) hypothetical $0.08/GB-month region and 30-day month; baseline IOPS/throughput only.                                                                              | $0.75             |
| Bedrock                  | `3.2 × P_input + 0.48 × P_output`, where prices are dollars per million tokens for the selected model/Region/tier from [Bedrock pricing](https://aws.amazon.com/bedrock/pricing/).                                                                          | Pending model     |
| Other required allowance | `C_other`: DNS/registration, TLS issuance, transfer, optional CloudWatch ingestion/storage, retained artifacts/snapshots, and taxes. Price the actual choices; these are not assumed free.                                                                  | Pending           |

The hosting subtotal is **about $4.92** before model and other costs. To show sensitivity only, hypothetical token rates of $1 input/$5 output per million make the model term $5.60 and the subtotal **$10.52 + C_other**. Those token rates are **not attributed to a selected AWS model**. At $3/$15 the same workload costs $16.80 in model use, making the subtotal **$21.72 + C_other**. Longer prompts, larger outputs and repairs increase cost. Leaving the host on for 720 hours at the same example rates gives about **$20.18 hosting** for a 30-day month before model and other costs.

Do not confuse shutdown with teardown: [stopped EC2 instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html) retain billable storage, and a retained public IPv4 remains chargeable. Treat estimate uncertainty, separately budgeted qualification and a chosen contingency as explicit terms: `authorized ceiling >= hosting + demo tokens + qualification + C_other + contingency`. The owner must supply the actual ceiling and eligible remaining credits; this formula grants no budget.

### Spending controls required before paid use

Use AWS Budgets actual/forecast alerts at owner-approved thresholds and check billing after each scheduled run. AWS says [budget data/notifications are delayed](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html); they cannot enforce an immediate hard stop.

Require a server-side preflight reservation against the approved Bedrock allowance using a conservative token/price upper bound, bounded requests/retries and one in-flight paid call. Reconcile returned token usage; retain reservation for uncertain outcomes until reconciled. Persist accounting across restarts and refuse paid work when the remaining allowance cannot cover a call. Monitor a call-count limit as an additional safeguard, not a substitute for token cost. Retain a tested inference-disable switch and owner-operated host shutdown procedure. Existing OpenRouter limits remain unchanged and separate; this design grants no increase or provider calls. The proposed AWS ledger/control still needs implementation and verification.

## Alternative if host maintenance is unacceptable

Use one ECS Fargate task containing the proxy, Agent and Storefront, behind an Application Load Balancer with HTTPS and the same two hostnames. [ECS task roles](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html) provide runtime AWS credentials. This reduces host maintenance, but adds image registry, load-balancer/certificate/network configuration, a separate durable spending-ledger choice and more teardown items. It does not fix shared carts or make task restarts durable; use one task with controlled stop/reset/replacement rather than overlapping stateful deployments.

Cost it as `task hours × (vCPU rate + memory rate) + ALB hours + LCU usage + public IPv4 hours + registry/log/storage/transfer + model usage`, using [Fargate pricing](https://aws.amazon.com/fargate/pricing/) and [ALB pricing](https://aws.amazon.com/elasticloadbalancing/pricing/). Network placement determines task IP, NAT or endpoint charges; count the ALB's addresses too. Do not claim this alternative has the EC2 subtotal. ALB defaults to a [60-second idle timeout](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/edit-load-balancer-attributes.html); SSE requires tested heartbeats/timeouts here as well. Select this alternative only if its operating benefit justifies the additional services and fixed cost.

## Privacy, operations and acceptance work

Keep server certificate keys and any separately approved speech/provider secret outside the repository and built artifacts, in restricted server files on encrypted storage or an explicitly justified secret service. Keep the client CA signing key off the application host. Prefer no external-provider secret in the Bedrock-only demo. Separate deployment/admin permissions from runtime permissions; expose administration only through an approved restricted channel.

Propose redacted operational logs containing release/model versions, correlation IDs, status, latency, token counts and estimated cost; exclude message bodies, Snapshot values, credentials, cookies and Sensitive Fields. Bound local log size and propose seven-day retention, with separately approved sanitized evidence exports. [Bedrock invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html) can record inputs/outputs and is disabled by default; verify the eventual account setting and leave it disabled unless explicitly justified. Do not infer provider retention/privacy terms solely from this switch.

For CAP-06, prepare versioned infrastructure/configuration and reproducible artifacts from an identified commit, health checks for both stateful services, a previous artifact for rollback, an inventory of every resource, and an expiry/teardown date. Rollback closes admission and follows the same full reset contract; it never resumes an old pending Mutation. Protect the non-resetting cost ledger during rollback. Record actual deployment parameters and secret references without secret values.

CAP-07 acceptance must exercise:

- Unauthorized browser, certificate, host and session access; prohibited development routes; HTTPS iframe/CSP/CORS and exact message-source validation.
- Off-origin navigation, Sensitive Field redaction, bound/expired/reused Confirmation, stale/duplicate Actions and cross-session attempts through the deployed endpoints.
- SSE idle/reconnect/Stop, refresh during a Mutation, lost ActionResult, Agent-only failure, Storefront-only failure, whole-host restart, participant turnover and rollback. Uncertain Actions must never replay automatically.
- Model denial/throttle/timeout/malformed output, exhausted allowance and ledger loss; safe pause/fallback and a demonstrably effective inference-disable switch.
- Measured latency/memory, qualified Bedrock behavior and actual cost under the approved workload. Preserve failed attempts and distinguish development qualification from honest unseen evaluation.

Teardown must close admission and stop inference first, retain only authorized sanitized evidence, then terminate the dedicated instance and verify volume `DeleteOnTermination` behavior. Delete any retained volumes/snapshots/images, release the public IPv4, remove dedicated DNS entries and demo credentials/role attachments, and remove task-specific logs/secret resources after retention requirements. AWS documents [termination and attached-volume behavior](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/terminating-instances.html). Do not delete shared account resources. Finally inspect the tagged inventory and subsequent billing for residual charges; a terminated host alone does not prove zero ongoing cost. This is a future runbook outline, not executed teardown.

## Inputs needed to finalize CAP-04

| Decision               | Proposed starting point                                                             | Still required                                                                                       |
| ---------------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Audience and isolation | Scheduled supervised browser; one admitted session per instance                     | Actual evaluators, locations, concurrency and approval of the access/reset experience                |
| Account and Region     | Dedicated project resources in one Region                                           | Account owner, permitted account/Region, organization restrictions and authorized account inspection |
| Model                  | Regional on-demand Converse where supported                                         | Exact model/version/profile, access prerequisites, token rates and CAP-05 qualification              |
| Hosting                | One EC2 Linux host; candidate `t3.small`                                            | Owner choice versus Fargate, measured capacity and exact regional quote                              |
| DNS/TLS/access         | Two owner-controlled HTTPS subdomains; client certificate plus IP restriction       | Domain, issuance/renewal/delivery/revocation method and supported browser proof                      |
| State and retention    | Controlled full reset; separate persistent spending ledger; seven-day redacted logs | Owner acceptance, implementation design and failure tests                                            |
| Cost                   | Explicit hosting, token, qualification and other-cost terms                         | Remaining eligible credits, total authorized spend, contingency, alert recipient and expiry date     |

After those inputs, replace placeholders with a priced architecture and reviewable implementation/runbook. Explicit spending/provisioning authorization remains separate. **CAP-04 is not closed by this brief.**

All external references are primary AWS/vendor/browser documentation accessed **2026-10-06**. Service, model and price claims must be rechecked at the actual decision date. This work used public documentation and local repository reads only; no AWS account reads, subscriptions, inference, resources or spending occurred.
