# CAP-04 network and cost refresh — 19 October 2026

Public-source research only; no account calls, resources, DNS changes, subscriptions
or inference. **The owner’s selected console Region is `eu-north-1` (Stockholm)**; `us-east-1`
prices below remain comparison references. This is not an AWS quote, spending
permission or a claim of account entitlement. Existing local
five-Shopper evidence does not establish EC2 capacity.

## Account and service boundary

The owner’s 19 October screenshots, relayed during this session, show **Free account
plan, $100.00 remaining, $0 current-month spend, 171 days remaining, ending 7 April
2027**. Activities show 0/5 completed and $0/$100 earned. Offered rewards are not
balance; do not launch RDS or invoke a model to earn them. Screenshots also show
the **new AWS experience** (Projects/Team/Billing); its documented project rules
therefore apply. Individual credit expiry, covered services, quotas and model
access remain unverified. The owner can open the Bedrock catalogue (54 models
shown); catalogue visibility is not Invoke entitlement or quota evidence. No
account identifier or private console URL is retained. The owner subsequently confirms gpt-oss-20b details and the CloudFront dashboard open normally; this still does not establish model invocation or specific certificate/distribution feature authority. Confirm the project home Region in Settings before resource creation.

AWS says a Free account closes after six months or credit exhaustion, whichever
comes first. Paid accounts can incur charges beyond credits. Preserve Free; do not
join Organizations, enable Control Tower or use another documented automatic
upgrade trigger. [Account-plan rules](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).

The limited-rollout **Sign up for AWS (new)** matrix lists EC2/EBS/VPC, CloudFront,
Lambda, DynamoDB, S3, CloudWatch and Bedrock in its Free selection. It excludes
Lambda@Edge and multi-/cross-Region features. This matrix describes that signup
experience; it does not prove that every feature is enabled for this owner.
CloudFront **flat-rate plans, including the $0 plan, require a paid account** and
are excluded. Ordinary CloudFront pay-as-you-go is a separate candidate. AWS lists
`t3.small` among the post-15-July-2025 credit-supported instance types.
[Service matrix](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html),
[flat-rate eligibility](https://docs.aws.amazon.com/PricingPlanManager/latest/UserGuide/plans.html),
[EC2 eligibility](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/LaunchingAndUsingInstances.html).

Regional resource creation is locked to the project Region. Changing contact
details does not change it; activating advanced features requires a **Paid-plan
upgrade**, so it is outside this project’s constraint. Global services have an
exception; AWS specifically warns that CloudFront features creating resources
outside the project Region can be unavailable. The published managed Region SCP specifically excepts `acm:*` and `cloudfront:*` from its `us-east-1` deny, and its Free policy separately blocks exportable certificate requests. Non-exportable CloudFront viewer ACM certificates are therefore not categorically excluded by the documented Region policy. This is policy interpretation, not a grant of IAM permission or proof that this owner can request a certificate. Read-only account-page visibility and eventual separately authorized issuance remain acceptance checks.
[Project Region rules](https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html),
[advanced-feature upgrade prerequisite](https://docs.aws.amazon.com/accounts/latest/reference/activate-advanced-features.html),
[published project/Free managed policies](https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html).

Bedrock APIs that do **not** create resources have a documented exception allowing
all enabled-by-default commercial Regions. Direct invocation of a regional model
endpoint is distinct from a geographic/global inference profile; do not infer that
the project lock forces all inference into Stockholm or enables cross-Region
profiles. Current model cards show **In-Region Stockholm support for Nova Lite,
gpt-oss-20b and gpt-oss-120b**. Start qualification planning there; US endpoints are
only a documented alternative pending account access, network cost and latency.
[Nova Lite](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-lite.html),
[gpt-oss-20b](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-oss-20b.html),
[gpt-oss-120b](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-oss-120b.html).

## Subsequent account evidence and selected candidate

The owner subsequently reached a Virginia ACM restriction modal: the project is assigned to Stockholm and access to other commercial Regions requires upgrading the plan then activating advanced features. The generic policy exception described above did not establish actual console access. Do not try a certificate-creation API as a workaround. The owner explicitly selected the [Stockholm amendment](../specs/2026-10-19-cap04-stockholm-ingress-amendment.md): direct Caddy public ACME HTTPS for app/store, generated CloudFront hostname only for startup/control, regional S3/Lambda/DynamoDB. This avoids Virginia ACM/custom aliases. The relevant direct-plus-wake scenarios are approximately USD26.99 at 120 running hours / USD55.50 continuous; no main-shopping CloudFront transfer/request increment is added. The two-distribution candidate and its USD57.20 figure below remain comparisons, not the selected route. Account feature/credit/DNS checks still apply; no resources were created.

## Conditional topology recommendation

| Candidate                                                               | Ingress and egress                                                                                                                                                                                                                                                                                              | Decision implication                                                                                                                                                                                                                                                                                                                                   |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Direct EC2 HTTPS; manual start/prewarm                                  | Both approved sibling names point to one retained EIP; Caddy terminates trusted HTTPS. A public subnet, IGW route and outbound HTTPS support maintenance, deployment artifacts, administration and regional model endpoints without NAT. Restrict administration separately.                                    | Smallest baseline. Prefer this if manual availability is acceptable or optional wake services are unavailable. While stopped, the host cannot serve its own waiting page. Certificate issuance/renewal and actual public-browser acceptance remain required.                                                                                           |
| Two pay-as-you-go CloudFront distributions; protected public EC2 origin | Preserve `app.scpilot.tech` and `store.scpilot.tech`. Restrict origin ingress to CloudFront’s origin-facing prefix list **and** a checked secret origin header; the prefix list alone admits other distributions. Retain outbound public HTTPS for maintenance/model traffic. Price the EIP even while stopped. | Useful if an independent S3 waiting page and Lambda control path are needed. Define separate waiting/control behaviors and stopped-origin error handling; do not cache personalized HTML, API, cookies or SSE. Requires ACM viewer certificate in `us-east-1` plus separately valid origin TLS/name routing. No flat-rate bundled WAF/DNS assumptions. |
| CloudFront VPC origin; private EC2                                      | Private origin connectivity does not provide outbound connectivity. Requires IGW attached to VPC, a supported subnet/AZ and service-managed ENI. S3/DynamoDB gateway endpoints cover those services only; Bedrock/SSM endpoints do not provide general package-registry or OS-update egress.                    | Defer selection until a complete maintenance/deployment/admin/model egress design is priced. Do not add a standing NAT gateway merely for wake. IPv6-only egress needs actual endpoint/package compatibility proof.                                                                                                                                    |

These are design recommendations, not tested cloud connectivity. AWS documents
origin restrictions using [custom headers](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/add-origin-custom-headers.html)
and the [managed prefix list](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/LocationsOfEdgeServers.html#managed-prefix-list).
Public IPv4 plus an IGW route is described in [VPC internet access](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Internet_Gateway.html).
Current [VPC-origin requirements](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)
include `eu-north-1`, and `us-east-1` **except AZ ID `use1-az3`**; this is regional availability, not
owner access. That page no longer lists WebSockets among exclusions; do not reuse
an older categorical restriction as current evidence. SSE still needs deployment
acceptance. No extra service-managed private-ENI address fee is documented there.

For CloudFront SSE, distinguish origin **read timeout** (first packet and gaps;
default 30 seconds) from **response completion timeout** (whole response). An unset
completion timeout imposes no total maximum; a configured 60-second completion
timeout ends a long stream even with heartbeats. Send packets comfortably inside
the chosen read timeout, disable buffering/caching, forward event cursor and
required authorization/Origin headers, then verify reconnect without Action replay.
GET retry behavior is not permission to replay a Mutation.
[Timeout semantics](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesOrigin.html),
[VPC-origin API defaults](https://docs.aws.amazon.com/cloudfront/latest/APIReference/API_VpcOriginConfig.html).

## Refreshed reference prices

Read directly from AWS public price catalogs on **19 October 2026**. Rates are
before credits/free allowances/tax. Unless stated otherwise, effective date is
**1 October 2026**; publication dates are shown to distinguish freshness from the
effective tariff. CloudFront uses viewer edge geography, not the EC2 Region.

| Category                                  | Verified rate and catalog publication                                                                                                                                                                              |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Linux shared-tenancy On-Demand `t3.small` | **$0.0208/running hour**, SKU `QA3NBPZEQKZ2K9AR`; EC2 published 15 October. Configure Standard CPU credits: Unlimited is default and Linux surplus credits cost $0.05/vCPU-hour.                                   |
| gp3 baseline                              | **$0.08/GB-month**, SKU `JG3KUJMBRGHV3N8G`; EC2 15 October. 3,000 IOPS / 125 MB/s included; do not provision paid extras.                                                                                          |
| Public IPv4 / retained EIP                | **$0.005/hour**, same rate in use or idle; VPC published 16 October. A stopped host retains its EIP and associated charge; auto-assigned IPv4 is released on stop and can change on start.                         |
| Direct internet transfer out              | **$0.09/GB**, first 10 TB beyond global free tier; DataTransfer published 16 September, effective **1 June 2026**. AWS describes 100 GB/month aggregate free internet transfer, not a dedicated project allowance. |
| CloudFront pay-as-you-go                  | US HTTPS **$0.010/10,000**, Europe/Middle East **$0.012/10,000**; first-tier outbound **$0.085/GB US/Europe**, **$0.110/GB Middle East**; catalog 19 October. Functions: first 2M executions $0, then **$0.10/M**. |
| Lambda, x86 first tier                    | **$0.20/M requests + $0.0000166667/GB-second**; published 16 October. Function URL endpoint has no extra endpoint fee. No provisioned concurrency or extra ephemeral storage assumed.                              |
| DynamoDB Standard on-demand               | **$0.625/M WRU + $0.125/M RRU**; storage first 25 GB-month $0, then **$0.25/GB-month**; published 11 September, effective **1 August 2026**. Transactions and item-size rounding consume additional units.         |
| S3 Standard                               | **$0.023/GB-month + $0.005/1,000 PUT/COPY/POST/LIST + $0.0004/1,000 GET**; published 15 October.                                                                                                                   |
| CloudWatch Standard logs                  | **$0.50/GB ingestion + $0.03/GB-month storage**; published 7 October. Queries, detailed metrics, alarms and exports are separate.                                                                                  |
| Interface endpoint alternative            | **$0.01/endpoint-AZ-hour + $0.01/GB** first tier; VPC 16 October. One always-retained endpoint alone costs **$14.40/60 days** before data. S3/DynamoDB gateway endpoints have no additional charge.                |
| Bedrock ordinary regional On-Demand       | Input/output per million tokens: **Nova Lite $0.06/$0.24; gpt-oss-20b $0.07/$0.30; gpt-oss-120b $0.15/$0.60**; published 16 October. Rates are not model availability, suitability or subscription evidence.       |

Catalogs: [EC2 regional CSV](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv),
[VPC](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/us-east-1/index.json),
[DataTransfer](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/us-east-1/index.json),
[CloudFront](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudFront/current/index.json),
[Lambda](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/us-east-1/index.json),
[DynamoDB](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonDynamoDB/current/us-east-1/index.json),
[S3](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/us-east-1/index.json),
[CloudWatch](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/us-east-1/index.json),
[Bedrock](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/us-east-1/index.json).
Operational pricing rules: [T3 credits](https://aws.amazon.com/ec2/instance-types/t3/),
[EBS](https://aws.amazon.com/ebs/pricing/), [IPv4](https://aws.amazon.com/vpc/pricing/),
[stop/start persistence](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/how-ec2-instance-stop-start-works.html),
[EC2 transfer](https://aws.amazon.com/ec2/pricing/on-demand/),
[gateway endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html).
The generic T3 marketing table currently shows $0.0209 without a chosen regional
context; the explicitly regional Linux/shared catalog row controls this estimate.

**Stockholm prices also refreshed on 19 October:** EC2 `t3.small` **$0.0216/h**
(SKU `RZ2CPJT3JCVWXCQM`); gp3 **$0.0836/GB-month** (SKU `H33YTQG3Y9XKNSF3`),
same EC2 publication/effective dates. Lambda, IPv4, S3 and first-tier direct internet
transfer rates match the US table. DynamoDB **$0.67/M WRU, $0.1345/M RRU,
$0.269/GB-month after the first free 25 GB**; CloudWatch logs **$0.54/GB ingested +
$0.028/GB-month stored**. Nova Lite **$0.065/$0.26 per million input/output tokens**;
the two gpt-oss rates match the US table. Publications/effective dates match each
service above. These are separately read Stockholm rows, not US rates applied to EU.
Sources: [Stockholm EC2 CSV](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/eu-north-1/index.csv),
[Lambda](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/eu-north-1/index.json),
[DynamoDB](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonDynamoDB/current/eu-north-1/index.json),
[S3](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/eu-north-1/index.json),
[VPC](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/eu-north-1/index.json),
[CloudWatch](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/eu-north-1/index.json),
[Bedrock](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/eu-north-1/index.json),
[DataTransfer](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/eu-north-1/index.json).

## Complete illustrative 60-day bill of materials

Assume 1,440 elapsed hours, two normalized 30-day storage months, **20 GB total gp3
including OS/releases/catalogue/log headroom**, one retained EIP, and either 120
running hours (2 h/day including starts, maintenance and idle tail) or all 1,440.
This duty cycle is an assumption: a 60-minute idle timer does not guarantee it.
No free request/transfer allowances are deducted in this conservative arithmetic.

| Candidate manual/direct category, US reference                             | 120 running h / 1,320 stopped h | 1,440 running h |
| -------------------------------------------------------------------------- | ------------------------------: | --------------: |
| EC2 Standard compute                                                       |                          $2.496 |         $29.952 |
| gp3, retained throughout                                                   |                          $3.200 |          $3.200 |
| EIP, retained throughout                                                   |                          $7.200 |          $7.200 |
| S3 backup/release storage: average 1 GB, 1,000 PUT/LIST + 10,000 GET total |                          $0.055 |          $0.055 |
| Logs: 1 GB total ingestion + conservative 1 GB-month retained              |                          $0.530 |          $0.530 |
| 20 GB total outbound, including shopping/admin/maintenance; gross $0.09/GB |                          $1.800 |          $1.800 |
| Demo inference allocation, all interpretation/advice/repairs/retries       |                         $10.000 |         $10.000 |
| Separate qualification allocation                                          |                          $1.000 |          $1.000 |
| **Scenario total before contingency**                                      |                     **$26.281** |     **$53.737** |

Standing US **compute/storage/address subtotal** is `$10.40 + $0.0208 × running_hours`.
For a wholly stopped 60 days, EBS/EIP alone still consume **$10.40**; backup/log
retention and independently served waiting/control traffic remain additional.
Stockholm uses `$10.544 + $0.0216 × running_hours`; its logs scenario costs $0.568.
With the other stated allocations, Stockholm manual/direct totals are **$26.559
at 120 running hours** and **$55.071 continuous**. Its wholly stopped EBS/EIP floor
is **$10.544**. These include the same $11 inference/qualification allocations.
Do not hibernate or retain an unnecessary second root/data disk. More than 20 GB
required in deployment increases the estimate.

Inference allocation is a planning envelope, not a new permission or configured
ledger. At the historical 4,000-input/600-output average, 10,000 total calls cost
$3.84/$4.60/$9.60 for the three candidates respectively; 300 qualification calls
for **each** candidate total $0.5412. Stockholm Nova Lite instead gives $4.16 for
10,000 calls and $0.5508 for all three qualification batches combined. These are
average token scenarios, not bounds.
CAP-05 must qualify exact models/access and reserve worst-case billable tokens.

All remaining categories are explicit: existing external DNS/domain **$0 incremental
assumed**, subject to verified DNS access/provider policy; no Route 53 purchase.
Trusted ACME certificate is the direct-path proposal; CloudFront ACM non-exported
viewer certificates are the alternative. EBS encryption is included. IAM roles,
security groups, routes and IGW need no separately provisioned paid appliance.
Use basic monitoring and bounded local logs; the log allowance also covers optional
wake logs. EBS snapshots/AMI copies, customer-managed KMS keys, Secrets Manager,
WAF, Shield Advanced, API Gateway, load balancers, NAT gateways, interface endpoints,
ECR/CI services, scheduled managed orchestration, paid support, cross-Region copies
and persistent databases beyond the small optional control table are **not selected
($0)**. If any becomes necessary, add its full charge before selecting topology.
S3 storage above includes bounded catalogue backups, not restoring an old inference
allowance. Taxes/credit exclusions are account checks, not assumed covered.
[EBS encryption](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-encryption.html),
[ACM pricing](https://aws.amazon.com/certificate-manager/pricing/),
[credit exclusions](https://aws.amazon.com/awscredits/).

## Optional always-available waiting and wake path

Conditional design: S3 waiting assets through pay-as-you-go CloudFront; a separate
uncached control behavior reaches a regional Lambda Function URL; DynamoDB stores
invitation/lifecycle generation/lease state outside EC2. Keep Lambda outside the
VPC: it can call AWS control APIs without a NAT solely for wake. Use CloudFront OAC
with `AWS_IAM` and the documented invoke permissions to prevent bypass of the
distribution. Validate invitation and durable rate limits **before StartInstances**;
ordinary page/status traffic never starts EC2. Do not sleep in Lambda while booting.
[Function URL costs](https://docs.aws.amazon.com/lambda/latest/dg/furls-http-invoke-decision.html),
[CloudFront OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda.html).

Illustrative **additional** two-month workload, served even while EC2 is stopped:

| Incremental category                                                                                        | Gross estimate before free allowances |
| ----------------------------------------------------------------------------------------------------------- | ------------------------------------: |
| 100,000 Lambda invocations including denied/poll traffic, 128 MB, 200 ms each                               |                               $0.0617 |
| 100,000 billable RRU + 100,000 billable WRU; 0.01 GB control storage × 2 months conservatively at paid rate |                               $0.0800 |
| 100,000 additional S3 GET + 0.002 GB waiting assets × 2 months                                              |                               $0.0401 |
| 100,000 CloudFront HTTPS requests + 1 GB outbound at Middle East reference rates                            |                               $0.2300 |
| Optional 100,000 viewer Function executions, conservatively at post-free rate                               |                               $0.0100 |
| **Additional scenario total, rounded up**                                                                   |                             **$0.43** |

These incremental wake rows use US control-service rates; substituting the verified
Stockholm DynamoDB rates gives $0.08583 for its row and still rounds the combined
wake increment up to **$0.43**. This table counts waiting/control traffic only.
For the **two-distribution main CloudFront candidate**, replace the direct $1.80
transfer allocation with **20 GB main viewer transfer × $0.11 + 1M main HTTPS
requests × $0.012/10,000 + 1 GB separate admin/maintenance egress × $0.09 = $3.49**.
AWS-to-CloudFront origin transfer is waived; do not add it again. Viewer rates
depend on actual serving location; these Middle East figures are an explicit
scenario, not a global maximum. [CloudFront transfer rules](https://aws.amazon.com/cloudfront/pricing/).

CloudFront advertises **1 TB transfer + 10M requests/month account-wide** under
pay-as-you-go Free Tier; Lambda also advertises free monthly requests/compute.
These can reduce actual consumption but are not flat-rate entitlements or abuse
caps. Viewer geography, bot requests, polling, retries, table transactions and
logs must be counted. Invocation-level invitation rejection still incurs request
work; reserved concurrency limits simultaneous work/RPS, not two-month spend.
Finite request budgets and a disable/teardown procedure are required before public
exposure. [CloudFront allowance distinction](https://aws.amazon.com/cloudfront/faqs/),
[Lambda pricing](https://aws.amazon.com/lambda/pricing/),
[Function URL throttling](https://docs.aws.amazon.com/lambda/latest/dg/lambda-urls.html#urls-throttling).

The named services are publicly listed in the Free-plan matrix, but **Function URL,
CloudFront/OAC/Functions, DynamoDB and S3 feature access for this owner remains
unverified**. Function URLs are not available in every Region; confirm the selected
regional feature and account quota. Do not upgrade to make wake work. If eligibility,
remote lifecycle adapter, safe waiting routing or complete pricing fails, retain
manual start/prewarming and describe its availability limitation honestly.
[Function URL availability](https://docs.aws.amazon.com/lambda/latest/dg/lambda-urls.html).

With main CloudFront traffic and wake included as above, the continuous candidate
rounds up to **$55.86 US reference / $57.20 Stockholm**, leaving **$22.80** in the
Stockholm case within a proposed $80 envelope and a separate **$20** of the currently
evidenced $100 unallocated. These are contingency allocations, not hard AWS caps.
Actual credit applicability, expiry, project home Region, feature/model eligibility,
DNS editing access and a complete selected topology still block closure of Ticket 02;
public-source arithmetic alone cannot close it. Deployed capacity, public-domain
TLS issuance/operation and cloud lifecycle behavior belong to CAP-06/07 acceptance,
not this no-resource feasibility gate. **Next:** use Stockholm as the
resource baseline, verify DNS editing and the detailed credit/feature evidence,
then choose direct/manual if the CloudFront/ACM/wake features cannot be established
without upgrading. Re-price any added requirement before provisioning.
