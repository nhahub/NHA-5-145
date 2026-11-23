# CAP-04: credit-only deployment constraints

**Updated:** 19 October 2026. **Status:** owner constraints recorded; design and deployment remain open.

See the [current design revision](specs/2026-10-11-cap04-cloud-readiness-design.md) for SQLite, shopper restart semantics, public-ingress options and remaining proof requirements. The pricing table below remains a historical scenario, not the selected network design.

Fresh owner screenshots on 19 October confirm USD100.00 remaining, USD0.00 current-month cost,171 days remaining and plan end 7 April 2027. Additional activity credits are USD0 of 100 earned (0 of 5 activities). The selected console Region is eu-north-1 (Stockholm), and new project-based Billing explicitly confirms Free plan and USD0 due. Bedrock catalogue access works; exact-model invocation authority and credit-specific eligibility/expiry remain unverified. See [current evidence ledger](cap04-account-feasibility.md). The earlier price scenarios below are historical; use the [19 October Stockholm-aware network-cost refresh](research/2026-10-19-cap04-network-cost-refresh.md) for current reference inputs. The earlier two-distribution main-delivery candidate is approximately USD57.20 continuous. After AWS explicitly blocked Virginia ACM, the owner selected [direct Caddy HTTPS on the shopping domains plus a generated CloudFront startup link](specs/2026-10-19-cap04-stockholm-ingress-amendment.md): approximately USD26.99 at 120 running hours / USD55.50 continuous over 60 days under the stated workload, before contingency. Feature/account evidence and the final handoff remain open; no provisioning is authorized.

## Owner decisions

The owner created a personal AWS account during this planning session. Their console screenshot shows the **Free account plan, $100.00 credits remaining and 183 days remaining, ending 7 April 2027**. This is screenshot evidence, not an account audit. Their constraint is **$0 out-of-pocket spending**. They want a public link for independent testers for approximately two months. On 14 October the owner supplied the purchased `scpilot.tech` domain (.tech Domains), replacing the no-domain constraint. Registration is an owner-completed purchase outside this AWS estimate; no additional paid DNS, certificate, renewal or account upgrade is authorized. Use [the domain/HTTPS preparation](cap04-domain-https-plan.md) and the approved sibling-origin layout. These decisions replace the supervised, owner-domain assumptions in the [6 October draft](cap04-aws-design-draft.md).

The advertised $200 is not the current balance or authorization to charge a payment method; only $100 is presently evidenced. Resource creation, subscriptions, account upgrades and inference remain separate future actions.

## Can the credits cover two months?

The small-host workload appears affordable, but a complete public deployment has not been priced or verified. Use **$100** as the initial planning ceiling: eligible new customers receive $100 at signup; the additional $100 depends on activities. Preserve the **Free account plan**, which ends at six months or credit exhaustion. A Paid account plan can charge beyond credits. The screenshot confirms the plan end date; individual credit expiry/applicability remains a separate Billing check. [AWS plan comparison](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html), [Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/).

Reference Region: `us-east-1`, not yet selected. This **60-day continuous-running estimate** uses 1,440 hours and two 30-day storage months. Rates and model details are in the [pricing research](cap04-pricing-research.md). No account entitlement or quota has been checked.

| Component                              | Calculation            | Estimated credit consumption |
| -------------------------------------- | ---------------------- | ---------------------------: |
| Linux `t3.small`, standard CPU credits | 1,440 × $0.0208        |                      $29.952 |
| One public IPv4                        | 1,440 × $0.005         |                       $7.200 |
| 20 GB gp3, baseline performance        | 20 × $0.08 × 2         |                       $3.200 |
| Hosting subtotal                       | Rounded after addition |                   **$40.35** |

For illustration, **10,000 total model calls** over 60 days averaging 4,000 input and 600 output tokens consume 40 million input and 6 million output tokens. This includes interpretation, advice, repairs and retries, not 10,000 shopper messages. These averages are assumptions, not measured token bounds.

| Candidate, pending qualification and account access | Demo model estimate | Separate 300-call qualification | Hosting + both workloads |
| --------------------------------------------------- | ------------------: | ------------------------------: | -----------------------: |
| Amazon Nova Lite v1                                 |               $3.84 |                         $0.1152 |               **$44.31** |
| OpenAI gpt-oss-20b on Bedrock                       |               $4.60 |                         $0.1380 |               **$45.09** |
| OpenAI gpt-oss-120b on Bedrock                      |               $9.60 |                         $0.2880 |               **$50.24** |

These totals exclude the unresolved public HTTPS path, logs, transfer, backups, optional services and non-credit-covered charges. They are **not an all-in quote**. No domain purchase, paid speech, NAT gateway, load balancer or GPU training host is included. Keep offline training on the owner's local RTX 3060. A proposed internal envelope of **$80 in eligible credits** would leave $20 of the initial $100 unallocated; adopt it only after pricing public access. It is not a billing cap or spending authorization.

Recommendation: **finish local cloud-readiness work before deploying resources**, then run a short rehearsal before starting the public demo window. There is no present cost-based reason to wait until the final submission week. Documentation is due 16 October, implementation 30 November and the final demonstration/reports 4 December; expiry must cover the chosen window.

## Public-link design changes needed

The original shared-cart limitation is addressed by the local
[shopper-isolation implementation](shopper-isolation-verification.md), whose final
verification is recorded separately. State remains ephemeral and anonymous.
The earlier client-certificate/IP-allowlist proposal does not provide the requested
shareable public experience. Resolve and verify these items before exposure:

1. Server-issued shopper identity and authorization binding browser, Agent session, cart, fictional orders and mutation authority. Every read, Action, ActionResult, Confirmation and Undo must respect ownership. Caller-supplied IDs and CORS alone are insufficient.
2. Independent shopper state, expiry and measured concurrency limits. Ephemeral state remains acceptable for a graduation demo with explicit reset notices and fresh authority after restart. Never replay uncertain Actions. If parallel public use cannot be made safe within scope, keep deployment pending.
3. Verified domain-free HTTPS entry points preserving distinct Panel/Storefront origins, secure origin connectivity, iframe/cookie behavior, SSE and microphone support. An EC2 HTTP address or untrusted certificate is not sufficient. Do not assume CloudFront's $0 flat-rate plan works on a Free AWS account; service-plan and account-plan eligibility differ.
4. Server-side request/token/concurrency limits and a durable global inference allowance. Decide and test admission/abuse controls: creating new browser sessions must not bypass the global limit. A publicly reachable demo need not grant unlimited model calls.
5. Existing origin, Sensitive Field, bound Confirmation, stale/duplicate Action and refresh-recovery guards; protected operational routes; bounded redacted logs and an inference-disable switch.

This is cloud-readiness work for the Controlled Storefront, not a general retailer platform. CAP-05 must still qualify the model on the project's languages and structured contract; cheap inference does not establish accuracy.

## Financial and account gate

Stay on the Free account plan; do not upgrade to unlock a service. If a required model or hosting path is unavailable, revise the design or leave the gate open. Do not create/join AWS Organizations or enable Control Tower: AWS documents upgrade and credit-loss consequences. Verify the actual signup experience and credit applicability before selecting a model or accepting provider terms. [AWS Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/).

Budget notifications are delayed and cannot guarantee a card-spending ceiling on a Paid account. Application limits control inference, not infrastructure bills. Keep a resource inventory, teardown date and local evidence copies before Free-plan closure. [AWS Budgets limitations](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).

Next: implement the approved sibling-domain HTTPS configuration, verify model access and settle the all-in credit envelope locally; recheck the Free plan, remaining balance, credit applicability and expiry before provisioning. The existing account needs no reversal or upgrade. CAP-02/03 are closed under the approved synthetic benchmark scope; independent human evaluation remains a disclosed limitation. No AWS account access, resource, inference, subscription or upgrade occurred for this document.
