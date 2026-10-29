# CAP-04 account and network feasibility

**20 October 2026 — in progress; local Ticket 02 remains open.** Local combined
readiness Ticket 08 is resolved. This document records account evidence and the
remaining decision gates; it does not authorize provisioning, a Paid-plan upgrade,
subscription acceptance, DNS changes or inference.

## Model access update — 20 October

The owner successfully opened ordinary CloudShell. Their model availability GET
and the agent's subsequent local SDK GET independently confirm AUTHORIZED plus
AVAILABLE agreement, entitlement and Region for openai.gpt-oss-20b-1:0 in Stockholm.
The current-user CLI and optional CRT dependency are installed; browser login
uses a separate cap05-stockholm profile, with no access-key sharing. This resolves
the named candidate's read-only eligibility uncertainty, not its actual inference,
quality, quota or billed cost. See the [diagnostic proposal](cap05-diagnostic-protocol.md).
Two separately approved diagnostic attempts subsequently failed, the second with
ThrottlingException / HTTP429. Read-only applied quotas show zero GPT-OSS20B
on-demand requests/minute and tokens/minute, plus zero Nova Lite on-demand
shortlist quotas. The account-specific cause is unknown. USD0.03 remains held
across USD0.04 cumulative authorization, actual cost unknown, both ledgers
disabled. No further call is approved. No application deployment, DNS write,
quota increase request or upgrade occurred. See the
[preserved quota evidence](../eval/evidence/cap05-diagnostic-20261020/quotas.json).

## Owner continuation — 20 October

The owner could not reach Billing Support and instructed continuation with the
available evidence. Record public IPv4 credit coverage as unresolved and do not
repeat the Support request as a gate to further preparation. The [conditional
handoff](cap04-deployment-handoff.md) carries that uncertainty into offline
CAP-05/06 preparation. This does not turn an unknown into verified coverage,
authorize cash charges or an upgrade, close local 02, or permit paid inference,
resource creation or DNS writes. Those execution steps retain separate gates.

## Evidence ledger

| Input                | Evidence currently available                                                                                                                                 | Status                                                                                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Account plan         | Owner Billing screenshot 19 October explicitly Current plan Free                                                                                             | Confirmed screenshot evidence; no upgrade performed                                                                                                       |
| Remaining credit     | USD100.00 remaining; USD0.00 due in Billing; USD0.00 current-month dashboard                                                                                 | Confirmed screenshot balance; not a live API audit or USD200 allowance                                                                                    |
| Plan end             | Current screenshot: 171 days remaining, 7 April 2027                                                                                                         | Plan end evidenced; separate from individual credit expiry                                                                                                |
| Credit eligibility   | Owner screenshots list Bedrock, Elastic Compute Cloud, Lambda, DynamoDB, Simple Storage Service, CloudFront and CloudWatch                                   | Listed applicability evidenced; VPC/public IPv4 coverage unresolved; not resource/model authority                                                         |
| Credit dates         | Owner screenshot: start 7 October 2026; expiration 7 October 2027, 15:41 (UTC+00:00)                                                                         | Individual credit expiry confirmed, distinct from Free-plan end 7 April 2027                                                                              |
| AWS Region           | Owner console URL selects eu-north-1 (Europe/Stockholm)                                                                                                      | Stockholm project assignment explicitly confirmed by the subsequent AWS restriction modal                                                                 |
| Account experience   | Owner screenshots show project switcher, Projects/Team and new Billing page                                                                                  | New project-based signup experience evidenced; its restrictions apply                                                                                     |
| Service access       | Owner screenshots show Lambda, DynamoDB, ACM and CloudFront pages; VPC dashboard explicitly reports Stockholm                                                | Visibility evidenced; VPC list shows one Available VPC; action permissions and EC2/EBS/S3/admin checks remain pending                                     |
| Bedrock model access | Owner CloudShell and local SDK availability API both return AUTHORIZED and AVAILABLE agreement/entitlement/Region for gpt-oss-20b in Stockholm on 20 October | Eligibility confirmed; two failed diagnostics, second HTTP429; applied GPT-OSS20B RPM/TPM zero; qualification and billing unverified                      |
| DNS                  | Owner DNS Records screenshot shows Add new record and A/CNAME categories for scpilot.tech                                                                    | Record-management access evidenced with no purchase prompt visible; no write or propagation verified; actual A/CNAME entries remain collapsed/uninspected |
| Local readiness      | Real proxy, release, allowance, lifecycle and capacity checks; physical Android local exception documented                                                   | Passed locally; not cloud qualification                                                                                                                   |
| Programmatic access  | Current-user AWS CLI2.38.2 and browser-approved cap05-stockholm profile; local Boto3 read-only model availability succeeds 20 October                        | Authenticated SDK access; two separately approved failed diagnostics; no application resource writes or account upgrade                                   |

Keep account IDs, billing address, payment details and credentials out of committed
evidence. Record only plan, dates, dollar balances, Region, observed access status
and redacted failure categories. Owner-supplied observations are labelled as such;
they are not a programmatic account audit.

## Screenshot reconciliation

The second 19 October screenshot shows 0 of 5 activities completed and USD0 of 100 additional credits earned. It offers USD20 each for EC2 launch, Bedrock playground, a cost budget, a Lambda web app and an Aurora/RDS database. These are unearned offers, not current balance or authorization to perform the activities. In particular, do not provision an unnecessary database or make a playground invocation just to collect a reward. SQLite on the existing disk remains the design.

A read-only recursive DNS check on 19 October still returns the four tech-domains OrderBox nameservers for scpilot.tech. app/store A and CNAME queries return NXDOMAIN; the apex CAA query returns no answer. This is a resolver observation, not authenticated zone inspection, and no records were changed.

Screenshots are owner-supplied observations. USD0 current-month cost and unavailable breakdown data do not establish absence of unbilled resources or global inventory. Stockholm project assignment and individual credit expiry are now evidenced. VPC/public IPv4 credit applicability and service/model entitlements remain unresolved.

## Read-only owner checks

1. Sign in to the existing account and inspect the Console home cost/usage widget
   or Billing Free Tier view. Record the current Free/Paid plan, credit balance
   and plan end. AWS documents these views for Free account information; this is
   not the older twelve-month EC2 Free Tier assumption.
   [AWS tracking guidance](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/tracking-free-tier-usage.html).
2. In the new experience, inspect Credits in AWS Settings if that view is available. The classic Billing Credits page is not assumed to exist for this project. AWS places Credits, invoices and spend limits in AWS Settings, with budgets/Cost Explorer in Billing and Cost Management. [New-experience billing layout](https://docs.aws.amazon.com/cost-management/latest/userguide/bcm-lite-cost-management.html). Inspect the current credit details. Record each relevant remaining
   balance, expiration date and applicable services, including Bedrock, compute,
   storage, delivery and control services. If details are unavailable, record
   unknown. Credits apply only to eligible service charges; a general balance is
   not proof that every design component is covered.
   [AWS credit application](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/useconsolidatedbilling-credits.html).
3. Record the selected Region and any project/Free-plan restrictions actually
   shown. Open the required service landing pages without creating resources.
   Do not select an upgrade, Organizations, Control Tower or an advanced-feature
   activation to unlock access. A denied page is evidence of a blocker, not a
   reason to bypass the Free-plan constraint. The published new-signup matrix is
   explicitly a limited rollout; its account applicability must be established.
   [AWS service matrix](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html).
4. For the agreed model shortlist, inspect account/Region-specific availability.
   Where an authorized current CLI/SDK is already available, the read-only
   `GetFoundationModelAvailability` API reports region, agreement, authorization
   and entitlement status. Listing models or seeing a card does not prove all
   four. Do not use a playground, inference request, agreement-creation action or
   subscription as an access probe. First invocation of applicable third-party
   models can initiate subscription handling.
   [Availability API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetFoundationModelAvailability.html),
   [Bedrock access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html).
5. Inspect the registrar's existing DNS-record management page for scpilot.tech.
   Confirm editing is included and record any existing app/store/CAA conflicts
   without changing them. No transfer or Route53 hosted zone is assumed necessary.

The owner supplied current plan/balance/plan-end screenshots and a console URL selecting Stockholm. The Bedrock model catalogue opens normally (owner reply and screenshot). This proves catalogue access only. The owner also opened gpt-oss-20b details without a visible upgrade block and confirms the CloudFront dashboard opens. These prove read-only console visibility, not model invocation or distribution/certificate/control-feature creation eligibility. No model invocation or subscription is requested. The catalogue Anthropic use-case notice is provider-specific and is not a requirement to submit information for the present non-Anthropic shortlist. Subsequent credit screenshots establish the dates and listed applicability below.

## Confirmed Virginia restriction and selected fallback

A subsequent owner screenshot shows the actual ACM Certificates list loading successfully with zero entries and no visible access error. The cropped screenshot does not show its Region. The owner then supplied the working tab URL, whose Region is eu-north-1: Stockholm certificate-list access is confirmed. us-east-1 list access remains unverified. The separate browser’s generic sign-in redirect is not proof of the authenticated list Region. The account/session-qualified URL itself is not retained. No certificate was requested.

Owner screenshots on 19 October confirm Lambda, DynamoDB and ACM landing pages open without a visible upgrade denial. Their cropped headers do not establish each page’s Region. The generic us-east-1 ACM deep link instead reaches a blank AWS sign-in session-selector page. That symptom is not an AccessDenied response and does not prove a paid-plan or Region restriction; the cause has not been established. No credentials, account-specific redirect URL or browser challenge parameters are retained.

Historical diagnostic (completed; do not repeat): try the existing working ACM tab in the same signed-in browser, replacing only the regional hostname segment eu-north-1 with us-east-1 and preserving its account/session prefix and ACM path. This is a navigation diagnostic, not an asserted fix or Region-creation authorization. Record the resulting Region or visible error. Retain the project session; do not request a certificate, change browser security settings, activate advanced features or infer Virginia access from the generic ACM landing page.

The next owner screenshot establishes the actual restriction: Virginia is unavailable, the project is assigned to Stockholm, and AWS requires upgrade then advanced features for other Regions. Treat this as a confirmed account-console blocker, not a blank sign-in symptom. Do not bypass it through an issuing API. The owner selected [automatic wake on the generated CloudFront hostname plus Caddy HTTPS for the owned shopping domains](superpowers/specs/2026-10-19-cap04-stockholm-ingress-amendment.md). Custom-domain CloudFront with Virginia ACM is not the selected path. No certificate request or account upgrade occurred.

The owner subsequently opened scpilot.tech DNS Records: Add new record and A/CNAME categories are visible with no extra-purchase prompt. No record was saved; nameserver/public-zone reconciliation and conflict checks belong before eventual DNS writes. The actual record sections are collapsed, so their contents are not inventoried.

The owner also opened the credit Applicable services dialog. Screenshots visibly list Amazon Bedrock, Amazon Elastic Compute Cloud, AWS Lambda, Amazon DynamoDB, Amazon Simple Storage Service, Amazon CloudFront and Amazon CloudWatch. The EC2 abbreviation search did not show compute, but its full name did. Both Virtual Private Cloud and VPC searches returned no match. This establishes neither coverage nor exclusion of public IPv4 charges; their billing classification and applicability require reconciliation. EBS is priced under the EC2 service catalog; do not require a separately named EBS entry without checking product naming. DynamoDB Accelerator and CloudFront Flat-Rate Plans also appear, but are not selected components. A credit listing does not establish Free-plan permission to create resources or select a pricing plan.

The individual credit screenshot shows a start date of 7 October 2026 and expiration of 7 October 2027 at 15:41 UTC. The Free-plan end remains 7 April 2027. The later credit date does not establish continued Free-plan service access after the earlier plan end. Neither date increases the confirmed USD100 balance or authorizes spending or an upgrade.

The subsequent owner VPC dashboard screenshot opens successfully and reports Stockholm: one VPC, three subnets, one route table, one internet gateway, one network ACL, one security group, zero NAT gateways and zero Elastic IPs. The VPC list shows one Available VPC. Its default status is not visible and is not inferred from the address range. These observations confirm read-only console/resource visibility, not public IPv4 credit coverage or creation authority. No resource identifiers are retained and no resources were changed.

Official-source follow-up confirms that public IPv4 in-use and idle address usage types are Amazon VPC billing codes. The documented new Free experience supports VPC, but that does not resolve the missing account-specific credit entry. See the [IPv4 coverage finding and precise Billing Support question](research/2026-10-19-cap04-ipv4-credit-coverage.md). Retain the IPv4 cost allowance; do not create a resource to test billing or mark this coverage gate passed.

## Project Region constraint

AWS documents that this new signup experience assigns each project a Region and hosts regional resources there. Changing contact details does not change it; different resource Regions require the separate advanced-features path. Do not activate that path under the no-upgrade constraint. Global services have exceptions. Bedrock APIs that do not create resources may be used in all enabled-by-default commercial Regions: this differs from geographic/global inference profiles, and still requires model/access verification. Consequently the previous us-east-1 price and model shortlist is a reference, not evidence that this project can create Virginia infrastructure or must invoke only Stockholm models. The published Region SCP excepts acm:_ and cloudfront:_ from its us-east-1 deny; the Free policy blocks exportable certificate requests. This supports the non-exportable viewer-certificate path at the policy level, without proving this owner has request authority. Confirm the project Region and account-page visibility; actual issuance remains a separate provisioning check. [Managed project policies](https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html). [AWS project Regions](https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html).

## Current reference scenarios

The [19 October official-source refresh](research/2026-10-19-cap04-network-cost-refresh.md) verifies Stockholm rates independently from the older Virginia reference. With 20 GB gp3, a retained EIP, bounded backup/log/traffic assumptions and USD11 allocated for inference plus qualification, the 60-day direct/manual candidate is USD26.559 at 120 running hours, or USD55.071 continuous. The CloudFront main-delivery plus optional-wake candidate is approximately USD28.68 at 120 running hours, or conservatively rounded USD57.20 continuous. These are conditional scenarios, not a selected architecture, quote, account entitlement or new inference spending authorization.

The continuous CloudFront/wake estimate leaves USD22.80 within a proposed USD80 planning envelope plus USD20 of the confirmed USD100 unallocated. A wholly stopped host still retains USD10.544 in EBS/EIP over 60 days before other storage/control traffic. No unused free request/transfer allowance or unearned reward credits are subtracted. Independent Decimal recomputation confirms the arithmetic. Duty cycle, viewer geography, tokens, bot traffic, account coverage and added services can change the result.

The owner subsequently chose direct shopping HTTPS plus a generated CloudFront waiting/control link to avoid the Virginia restriction. Add only the wake increment to the direct candidate: approximately USD26.99 at 120 running hours or USD55.50 continuous. See the approved amendment. Function URL/OAC, remote control authority, DNS editing and credit/access evidence remain prerequisites; manual start is fallback. This is a selected design, not approved provisioning or proof of cloud operation.

## Network and costing decision checklist

Compare direct EC2 HTTPS with custom-domain CloudFront public and VPC origins.
Use the approved sibling origins `app.scpilot.tech` and `store.scpilot.tech`.
Ordinary trusted public-domain TLS still requires deployed acceptance. A valid
CloudFront viewer certificate does not secure an unverified public origin hop.

For every candidate, account for both running and stopped hours: retained EBS,
Elastic IP, backups/artifacts, HTTPS delivery, logs, administration and OS/model
egress, inference/qualification, waiting page and durable control storage. Compute
savings do not imply storage or retained addresses become free when stopped.
Avoid a NAT gateway, standing wake server, ALB or paid flat-rate plan unless an
evidenced requirement and approved complete estimate warrant them.

Manual start and conditional Lambda wake must use the same invitation and
lifecycle safety contract. A tiny estimated Lambda execution cost alone does not
price its public endpoint, waiting assets, storage, logs or abuse traffic. Default
service concurrency and delayed billing alerts are not application spending caps.

Final selection requires current official rate inputs, explicit 60-day traffic
and token assumptions, stopped/running scenarios, contingency and confirmed credit
coverage. If optional wake is unavailable or exceeds the envelope, retain manual
startup and automatic safe idle shutdown. If required service/model access is
unavailable, leave Ticket 02 open; do not silently upgrade or switch providers.

Ticket 09 reconciles the final architecture only after this evidence is complete.
CAP-05 model qualification, CAP-06 provisioning and CAP-07 deployed acceptance
remain separate gates. Historical pricing is in [the earlier research](cap04-pricing-research.md);
it is not a fresh quote or permission to spend.
