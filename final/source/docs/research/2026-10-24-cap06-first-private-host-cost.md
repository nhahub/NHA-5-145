# First private inspection: gross AWS worksheet, 24 October 2026

Read-only public-primary-source lookup. No account API, credential, installation,
resource, model, role, schedule, alarm or automation operation was performed.
This is a proposed credit allocation, not creation approval or a billing cap.
Free plan and USD0 cash remain mandatory; do not upgrade the account.

The requested scope is one Stockholm Linux shared-tenancy t3.small, Standard CPU
credits, no paid software, at most two cumulative running hours; one ordinary
public IPv4 EIP allocated for at most two cumulative hours and then released;
one encrypted 20-GiB gp3 root volume, including the root itself, retained for at
most 60 days; baseline 3,000 IOPS/125 MiB/s only; and at most 0.01 GiB internet
egress. No other operator-created resources or model calls are included.

## Current verified public rates

| Item                                              |           USD rate | Exact primary source and identity                                                                                                                                                                                                                                             |
| ------------------------------------------------- | -----------------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Linux t3.small, no preinstalled software          |        0.0216/hour | [AWS EC2 Stockholm Linux page-pricing map](<https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/EU%20(Stockholm)/Linux/index.json>), rate RZ2CPJT3JCVWXCQM.JRTCKXETXF.6YS6EN2CT7; 2 vCPU/2 GiB, Linux/NA/No License required. |
| gp3 provisioned storage                           |    0.0836/GB-month | [AWS EBS page-pricing map](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ebs.json), EU (Stockholm), Storage General Purpose gp3 GB Mo; rate H33YTQG3Y9XKNSF3.JRTCKXETXF.6YS6EN2CT7.                                                                  |
| Ordinary public IPv4, in use or idle              | 0.005/address-hour | [AWS VPC Stockholm catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/eu-north-1/index.json), H24SU884XW7MB5WC and 2M69N79CPJC2EXZ3, effective 1 October 2026.                                                                                |
| Direct Stockholm internet egress, first paid tier |            0.09/GB | [AWS DataTransfer Stockholm catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/eu-north-1/index.json), DRTM7T5YA7E492Z3.JRTCKXETXF.Q3Z75P77EN, 0–10,240 GB, effective 1 June 2026.                                                      |
| Incidental symmetric KMS requests                 |   0.000003/request | [AWS KMS Stockholm catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/awskms/current/eu-north-1/index.json), 2S77H5MZU5BVWEXS, effective 1 July 2025.                                                                                                           |

The EC2/EBS maps report publication 23 October 2026, 22:13:55 UTC; the current VPC,
DataTransfer and KMS catalogs report 16 October, 16 September and 11 September,
respectively. Every response used above is retained with retrieval time, HTTP
headers, raw/decoded byte lengths and SHA256 receipts in this directory. The two
page-pricing maps are about 369 KB/595 KB decoded. The massive EC2 offer index was
not downloaded. The original first gzip response is retained as a diagnostic;
rate extraction uses the decoded files bound by the receipt JSONs.

## Arithmetic and candidate allocation

| Item                                                             | Explicit calculation      |      Gross USD |
| ---------------------------------------------------------------- | ------------------------- | -------------: |
| Compute                                                          | 2 × 0.0216                |     0.04320000 |
| EIP                                                              | 2 × 0.005                 |     0.01000000 |
| Single gp3 root, entire retention including initial running time | 20 × (60/30) × 0.0836     |     3.34400000 |
| Internet egress, deliberately rounded upward                     | 0.010738 priced GB × 0.09 |     0.00096642 |
| Incidental KMS planning provision, no free allowance subtracted  | 100 × 0.000003            |     0.00030000 |
| **Planning total, before tax/credits**                           |                           | **3.39846642** |
| **Headroom within proposed USD4.50 credit allocation**           | 4.50 − 3.39846642         | **1.10153358** |

The four requested compute/IP/storage/egress rows alone total USD3.39816642.
The KMS row avoids silently claiming that encryption-associated requests are free.
Its 100-request quantity is an explicit conservative planning provision, not an
observed or enforced request count. Repeated launches, restores or retries can
change it. No customer-managed KMS key or additional monthly key fee is proposed.
[AWS KMS pricing](https://aws.amazon.com/kms/pricing/) distinguishes free managed-key
creation/storage from chargeable requests, and its EBS example uses three initial
requests per volume. [EBS encryption requirements](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-encryption-requirements.html)
also describe service-created grants/identity-only roles; no operator-created
instance role is needed merely to attach the encrypted root volume.

AWS EBS pricing labels its binary storage unit GB and states GB = 1024^3 bytes,
so VolumeSize=20 GiB is charged as 20 of those storage units. Baseline gp3 IOPS and
throughput have no additional provisioned-performance charge. Storage persists
until deletion; stopping the instance does not stop it. Its published example
prorates over a 30-day month; the main total uses two normalized months.
[EBS pricing](https://aws.amazon.com/ebs/pricing/).

The exact invoice depends on service metering and billing-period treatment. To
avoid relying on two normalized months as a universal upper bound, a deliberately
more conservative storage sensitivity uses 60/28 months: 20 × 0.0836 × 60/28 =
USD3.582857142857… storage. With the other rows, total is USD3.637323562857…,
rounded up to **USD3.63732357**, leaving **USD0.86267643** inside USD4.50. This
28-day sensitivity is a planning calculation, not an assertion that AWS bills
every month as 28 days. Bind the actual creation/deletion dates before approval.

For egress, 0.01 GiB is 10,737,418.24 bytes. Pricing it as 0.010738 decimal GB
rounds upward and is conservative even if the metered transfer unit is binary;
the public transfer catalog only labels its unit GB. No free 100-GB transfer
allowance, free EBS capacity, unused KMS requests or credits are deducted.

## Controls and limits of the estimate

T3 launch defaults to Unlimited. Set CpuCredits=standard explicitly and verify it;
Standard throttles toward baseline as earned credits run out. This worksheet
does not include Unlimited surplus-credit charges and cannot be used if that
setting is wrong. [RunInstances credit specification](https://docs.aws.amazon.com/cli/latest/reference/ec2/run-instances.html),
[Standard mode](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-standard-mode.html).

The two running hours include boot, inspection and every running interval, with
the one-minute minimum for each start. Idle/unreachable running time still bills.
An EIP remains chargeable while allocated, even if idle or its instance is
stopped; disassociation is insufficient. Stop the owned instance, observe its
state and release the EIP within their separate planning windows. The single
root volume keeps accruing storage until its approved deletion, including while
the stopped instance remains. [Instance-state billing](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html),
[public IPv4 billing](https://aws.amazon.com/vpc/pricing/).

Set InstanceInitiatedShutdownBehavior=stop explicitly for guest shutdown/poweroff.
It does not control the StopInstances API. Halt does not stop the EC2 instance.
[Shutdown behavior](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_ChangingInstanceInitiatedShutdownBehavior.html).

A persistent guest systemd stop deadline is defense in depth, **not a hard AWS
billing cap**. This is an inference from AWS's guest responsibility and failure
semantics: user data is opaque input interpreted by the instance; if bootstrap
fails before timer installation, that timer cannot execute. Guest/hardware
failures can also prevent shutdown scripts from running. Persisting a timer does
not make it an independent AWS control plane. [User data](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html),
[shutdown-script limits](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/how-ec2-instance-termination-works.html).
AWS recommends operator EC2 console/CLI/API stops rather than relying on a guest
command. The coordinator's proposed direct, owned StopInstances and observation
before finishing remains necessary; no new cloud schedule/alarm/role is added.
[Stop/start guidance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html).

Published rates exclude applicable taxes/duties; the account's tax treatment was
not inspected. General promotional-credit terms exclude transaction-based taxes
and restrict credits to eligible services. The Free-plan documentation separately
states that a Free account incurs no charges and closes on credit exhaustion or
plan expiry. Preserve that plan and verify current eligibility/credit coverage
through the existing owner-controlled gate; this public worksheet does not
establish the account's balance, tax result or feature eligibility, and does not
authorize any Paid-plan transition. [Pricing tax statement](https://aws.amazon.com/ec2/pricing/on-demand/),
[credit terms](https://aws.amazon.com/awscredits/),
[Free-plan rules](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).

USD4.50 is therefore a fitting **estimated gross credit allocation under these
stated quantities**, including the storage sensitivity and incidental KMS
provision. It is not a guaranteed maximum bill or permission to spend cash.
Overruns in time, retained volumes/addresses, transfer, tax, retries, added paid
software or other account usage require a revised decision. No actual allowance,
model cap or owner-held credential was read or changed by this lookup.
