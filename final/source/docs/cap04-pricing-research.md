# CAP-04 AWS pricing and Free Tier research

Historical 7 October reference. The
[19 October refresh](research/2026-10-19-cap04-network-cost-refresh.md) supersedes
its freshness/account assumptions and adds verified Stockholm prices, the owner's
new project-based signup constraints, and complete running/stopped candidate costs.
See the [current evidence ledger](cap04-account-feasibility.md); neither note proves
account feature entitlement or authorizes provisioning.

**Checked: 7 October 2026. Proposal inputs only; CAP-04 remains open.** The owner now requires a personal account, zero out-of-pocket spend, two months of hosting, no purchased domain, and a public link for independent testers. The earlier [supervised-host brief](cap04-aws-design-draft.md) is not an approved public deployment. No account access, subscriptions, inference or resources were used for this research.

Owner update after research: a supplied console screenshot shows a newly created **Free account plan**, **$100 remaining** and a plan end date of **7 April 2027**. No programmatic account access occurred. Credit applicability and individual credit expiry remain unverified.

## Free account plan is the first gate

“Up to $200” is not a verified balance: eligible new customers receive **$100 initially**, and earn up to another $100 through activities. Some activities consume credits themselves. A **Free account plan** stops at six months or credit exhaustion, whichever comes first; AWS closes the account. A **Paid account plan with credits** can charge beyond credits or for uncovered services. Therefore the zero-cash requirement requires confirming the actual plan, creation/expiry dates, remaining eligible credits and service access before implementation or deployment. [AWS plan rules](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html), [earning credits](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans-activities.html).

Credits normally expire twelve months after account creation; that does not extend the six-month Free plan. Joining Organizations or setting up Control Tower automatically upgrades the account and expires Free Tier credits immediately. Other automatic upgrade triggers include Partner Network membership, Professional Services/Enterprise agreements, Skill Builder Team subscriptions and HIPAA/SEC designation. Do not perform these to unlock this project. Paid accounts cannot downgrade to Free. [Free Tier FAQs](https://aws.amazon.com/free/free-tier-faqs/), [upgrade triggers](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).

For accounts created from 15 July 2025, AWS explicitly lists `t3.small` among credit-supported EC2 types; `t3.medium` is absent and remains a price comparison, not a Free-plan recommendation. [EC2 eligibility](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/LaunchingAndUsingInstances.html). Bedrock is an eligible learning activity, but no individual account/model entitlement is proven. AWS's limited-rollout **“Sign up for AWS (new)”** service matrix allows Bedrock but excludes geographic/global inference; this additional restriction must be checked against the owner's actual account experience. [Service matrix](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html).

Credits cover only designated eligible services. General credit exclusions include Route 53 domain registration/transfer, Marketplace unless authorized, upfront commitments, certain support/services and taxes. Hosted-zone DNS is distinct from domain registration. Inspect the actual credit's applicability; do not assume every Bedrock offering is excluded merely because Marketplace access machinery exists. [Credit terms](https://aws.amazon.com/awscredits/). CloudFront's **$0 flat-rate plan requires a Paid AWS account**; it is not a way to preserve a Free account plan. [CloudFront plan requirements](https://docs.aws.amazon.com/PricingPlanManager/latest/UserGuide/plans.html).

## Verified reference rates

USD list prices, **us-east-1**, Linux shared-tenancy on-demand, no licence surcharge, credits, tax or discount subtracted. AWS's public [EC2 regional CSV](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv) returned effective date **2026-10-01**, SKUs `QA3NBPZEQKZ2K9AR` (small) and `NN4EGUUQRWVYP98C` (medium).

| Component                               | Rate / assumption                                | Earlier 14-day reference | 60-day reference |
| --------------------------------------- | ------------------------------------------------ | -----------------------: | ---------------: |
| `t3.small`, 2 vCPU / 2 GiB              | $0.0208/hour; 120 / 1,440 running hours          |                  $2.4960 |         $29.9520 |
| `t3.medium`, 2 vCPU / 4 GiB alternative | $0.0416/hour; same hours                         |                  $4.9920 |         $59.9040 |
| 20 GiB gp3                              | $0.08/GiB-month; 3,000 IOPS / 125 MiB/s baseline |                  $0.7467 |          $3.2000 |
| One retained public IPv4                | $0.005/hour; 336 / 1,440 hours                   |                  $1.6800 |          $7.2000 |
| **Small-host subtotal**                 | Excludes public HTTPS/front-door design          |              **$4.9227** |     **$40.3520** |
| Optional Route 53 zone                  | $0.50 per started billing month, first 25 zones  |              $0.50–$1.00 |      $1.00–$1.50 |
| Optional standard DNS queries           | $0.40/million, first billion/month               |        $0.004 per 10,000 |  Usage-dependent |

Storage estimates normalize to 30-day months; actual calendar dates and retained seconds matter. Regional gp3 rate: [AWS storage comparison](https://aws.amazon.com/blogs/storage/migrate-your-amazon-ebs-volumes-from-gp2-to-gp3-and-save-up-to-20-on-costs/); billing increments/baselines: [EBS pricing](https://aws.amazon.com/ebs/pricing/). [IPv4 pricing](https://aws.amazon.com/vpc/pricing/) applies while in use **or idle**. [Route 53 pricing](https://aws.amazon.com/route53/pricing/) does not prorate hosted-zone months. No domain/zone purchase is proposed.

Explicitly configure **Standard CPU credits**: T3 defaults to Unlimited, whose Linux surplus rate is $0.05/vCPU-hour. Standard can throttle when earned credits run out; benchmark capacity. [T3 rules and sizes](https://aws.amazon.com/ec2/instance-types/t3/).

Optional CloudWatch Standard logs cost **$0.50/GB ingested + $0.03/GB-month stored**, before any allowance; effective 2026-10-01 in the [regional price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/us-east-1/index.json), SKUs `96K55R2PV3ZZZ3AM` / `JRHJQ2UMPUB5K73A`. Queries, alarms and exports add costs. AWS's internet-egress allowance is **100 GB/month shared across services/Regions**, not dedicated to this project; do not assume unused allowance. [EC2 transfer rules](https://aws.amazon.com/ec2/pricing/on-demand/). Front-door traffic, TLS, snapshots, extra storage and abuse remain unpriced until the public architecture is selected.

## Bedrock qualification shortlist

All three have active model cards, Converse on `bedrock-runtime`, and direct in-Region `us-east-1` availability. These are candidates, not qualified Arabic interpreters. Use exact IDs, ordinary on-demand Standard inference, no caching/batch discounts and no implicit profile selection.

| Candidate / exact runtime ID                                                                                                        | Schema mechanism                                               | Input / output USD per million tokens |
| ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------: |
| [Nova Lite](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-lite.html), `amazon.nova-lite-v1:0`         | Client tool calling; native Structured Outputs **unsupported** |                         $0.06 / $0.24 |
| [gpt-oss-120b](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-oss-120b.html), `openai.gpt-oss-120b-1:0` | Native Structured Outputs supported                            |                         $0.15 / $0.60 |
| [gpt-oss-20b](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-oss-20b.html), `openai.gpt-oss-20b-1:0`    | Native Structured Outputs supported                            |                         $0.07 / $0.30 |

Prices were read from the public [Bedrock regional price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/us-east-1/index.json), published 2026-10-06, effective **2026-10-01**, usage types `USE1-NovaLite-{input,output}-tokens` and `USE1-gpt-oss-{120b,20b}-{input,output}-tokens`. These are base on-demand rows, not fine-tuning, safeguard, Mantle, Priority or Flex rows.

Nova's optional `us.amazon.nova-lite-v1:0` profile routes from Virginia to Virginia/Ohio/Oregon; direct invocation avoids that profile. The gpt-oss cards show no commercial geographic/global profile. Nova includes Arabic in its [service-card languages](https://docs.aws.amazon.com/pdfs/ai/responsible-ai/nova-micro-lite-pro/nova-micro-lite-pro.pdf); Egyptian Arabic, Franco-Arabic and project accuracy remain unproven for every candidate. [Structured Outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) supports only a JSON Schema subset; application schema/safety validation remains required.

Amazon models are not Marketplace products; gpt-oss lists product ID **N/A** in [AWS model parameters](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-openai.html) and uses [Apache 2.0](https://huggingface.co/openai/gpt-oss-120b/blob/main/LICENSE). AWS service/provider terms still apply. For applicable Marketplace models, first invocation can enable a subscription and accept terms; it is not a read-only access test. Do not grant runtime subscription permissions. [AWS access rules](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html).

## Workload arithmetic and decision limits

Planning averages of **4,000 input + 600 output tokens/call** give:

| Candidate    | 800 demo calls: 3.2M input + 0.48M output | Separate 300 qualification calls: 1.2M + 0.18M | Combined |
| ------------ | ----------------------------------------: | ---------------------------------------------: | -------: |
| Nova Lite    |                                   $0.3072 |                                        $0.1152 |  $0.4224 |
| gpt-oss-120b |                                   $0.7680 |                                        $0.2880 |  $1.0560 |
| gpt-oss-20b  |                                   $0.3680 |                                        $0.1380 |  $0.5060 |

These averages are **not hard limits**; include system/schema/history, reasoning, repairs and retries in billable tokens. Qualifying all three costs $0.5412 under this assumption, not one row. The 60-day small-host plus one-model combined subtotal is **$40.77–$41.41**, excluding the public front door and other charges. It is not a complete public-deployment quote or a zero-cash guarantee.

Public independent access requires a revised admission/isolation design and abuse limits; 800 calls cannot describe unlimited public traffic. Persist conservative reservations, bound total tokens/calls/concurrency, and stop before the authorized credit reserve is consumed. [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html) notifications are delayed and are not hard caps. Do not upgrade the account or provision until the owner verifies that the Free plan covers the full two-month window and selected services.
