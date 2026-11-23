# December invitation-only operation: fresh cost inputs

**Retrieved:** 4 November 2026 Cairo (3 November23:41 UTC onward).
Read-only public-source research; no AWS resource writes or model calls.
Agent Reach's Jina reader retrieved official documentation; AWS machine-readable
catalogues supplied regional rates. A read-only account-plan call failed with
expired CLI sign-in, so there is no new account-balance assertion.

## Sources and verified rates

| Item                                                                             |                                                                   USD rate | Primary source                                                                                                                                                                                                                                                                                                    |
| -------------------------------------------------------------------------------- | -------------------------------------------------------------------------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Stockholm Linux t3.small, no software, Standard CPU credits                      |                                                                0.0216/hour | [EC2 regional map](<https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/EU%20(Stockholm)/Linux/index.json>), `RZ2CPJT3JCVWXCQM.JRTCKXETXF.6YS6EN2CT7`.                                                                                                            |
| Stockholm baseline gp3 storage                                                   |                                                            0.0836/GB-month | [EBS regional map](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ebs.json), Stockholm `Storage General Purpose gp3 GB Mo`, `H33YTQG3Y9XKNSF3.JRTCKXETXF.6YS6EN2CT7`.                                                                                                                     |
| Ordinary public IPv4, idle or used                                               |                                                         0.005/address-hour | [VPC regional catalogue](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/eu-north-1/index.json), in-use/idle SKUs `H24SU884XW7MB5WC` / `2M69N79CPJC2EXZ3`. Stop does not release an EIP.                                                                                                |
| Stockholm Lambda x86 duration and requests                                       |                                        0.0000166667/GB-second;0.20/million | [Lambda regional catalogue](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/eu-north-1/index.json), `EUN1-Lambda-GB-Second` tier1 and `EUN1-Request`.                                                                                                                                   |
| Stockholm DynamoDB Standard on-demand                                            | 0.67/million WRU;0.1345/million RRU;0.269/GB-month storage above free tier | [DynamoDB regional catalogue](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonDynamoDB/current/eu-north-1/index.json), `EUN1-WriteRequestUnits`, `EUN1-ReadRequestUnits`, `EUN1-TimedStorage-ByteHrs`. Transactions multiply billable units; the worksheet quantities are units, not raw API calls. |
| CloudFront conservative cross-region rate used for tiny waiting/control delivery |                                        0.022/10,000 HTTPS requests;0.12/GB | [CloudFront pay-as-you-go pricing](https://aws.amazon.com/cloudfront/pricing/pay-as-you-go/). These deliberately exceed PriceClass100's normal US/Europe rates. Free tiers are not deducted.                                                                                                                      |
| EventBridge Scheduler                                                            |                                 1/million invocations after free allowance | [EventBridge pricing](https://aws.amazon.com/eventbridge/pricing/), Scheduler worked example. Worksheet does not deduct 14 million free invocations.                                                                                                                                                              |
| Direct Stockholm internet egress                                                 |                                                                    0.09/GB | [Official regional transfer catalogue](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/eu-north-1/index.json), outbound Stockholm to External, first paid tier, `DRTM7T5YA7E492Z3.JRTCKXETXF.Q3Z75P77EN`; freshly retrieved with a 10 GB planning quantity.                       |

EC2/EBS page-map publication:3 November 2026,21:10:38 UTC. Lambda publication:
30 October2026,23:42:55 UTC/effective1 October. DynamoDB publication:
11 September2026,12:44:22 UTC/effective1 August. The page maps arrived gzip-encoded;
decoded JSON was used, retaining the raw bytes separately. Fresh VPC catalogue
publication: 3 November 2026, 00:09:47 UTC; transfer: 3 November 2026, 13:31:47 UTC.

Temporary research receipts/raw responses are outside the repository at
`C:/Users/pc/AppData/Local/Temp/scpilot-public-plan-20261104/`. These are supporting
local research, not a publicly available or durable deployment evidence store.
Before approval/execution, retain the selected rate extracts with the protected
operating manifest. Decoded EC2 SHA256:
`68b6824fb1be6dd6b20ae21345b42ae4395b33e898e565c7a38d963e4ef2c609`;
EBS: `10f3185f0941ce535912ed31783f9692fa7423e71c29c705251ea154ecab2257`.

## Arithmetic and limits

Compute 768.25×0.0216=16.5942. EIP816×0.005=4.08.
Storage 20×0.0836×34/28=2.0302857143, deliberately using a conservative28-day
denominator rather than claiming every month is billed that way.
Lambda 77,000×(0.25×30×0.0000166667+0.0000002)=9.64041925.
This invocation quantity covers46,080 minute ticks,20,000 startup calls and
approximately 9,800 guard calls, rounded upward. Smaller real durations cost less.
One Lambda's 256 MiB allocation is0.25 GiB; no extra ephemeral-storage charge is
assumed with default512 MiB.

DynamoDB 5×0.67+10×0.1345=4.695. CloudFront 100,000/10,000×0.022+1×0.12=0.34.
Direct transfer 10×0.09=0.90. Scheduler 60,000/1,000,000=0.06.
Add 2.50 provision for small S3/logs/alarms/KMS/monitoring use and authority
storage. This last row is an allocation assumption, not a verified aggregate
service rate. TotalUSD40.8399049643, rounded upward per line for the proposal to
**USD 40.839906**, within the proposedUSD45allocation. No gross free allowance,
activity reward, provider credit or discount is subtracted.

This is a workload-conditioned planning estimate, not a hard billing maximum.
Uninvited requests can incur edge/Lambda/DynamoDB costs before refusal. Credit
reporting and alarms lag. No claim is made that a45-dollar resource budget
provides an AWS-side hard quota. Mandatory Free-plan status is the cash boundary;
do not upgrade the account to enable a feature.
[AWS Free-plan rules](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
state that the Free plan incurs no charges and closes on exhaustion/expiry.
Verify actual eligible credit balance/expiry before creation; other account
activity consumes the same credits. Provider inference is separately bounded
inside the original non-resettingUSD2 OpenRouter key cap, not paid by AWS credits.

## Independent closing mechanism: documentation checks

[Scheduler universal targets](https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-targets-universal.html)
accept a fixed AWS SDK action/JSON input and require an execution role with that
action. The proposal uses `arn:aws:scheduler:::aws-sdk:ec2:stopInstances` with only
the designated InstanceId; implement/validate its exact request before deployment.
The documented unsupported prefixes are read-only actions, not StopInstances.

[Schedule types](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html)
document finite recurring StartDate/EndDate and 60-second invocation precision.
One-time schedules use their `at(...)` expression/timezone, not StartDate/EndDate.
Therefore pin UTC timestamps, separate IAM start expiry from shutdown delivery,
observe actual EC2 stop and retain a guard/retry path. A schedule is not proof
that a shutdown happened, and guest timers alone are not independent cloud
controls. DNS TTL proof remains a separate prerequisite for address release.
