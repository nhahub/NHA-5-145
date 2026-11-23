# CAP-07 controlled host acceptance: 27 October 2026

The authorized session ended safely, with acceptance **incomplete**. It stopped at an operator log-quota fixture before application activation. The original host is stopped, its temporary EIP is released, and the Free plan remains active. No real model POST occurred. The [execution evidence](../eval/evidence/cap07-controlled-host-acceptance-20261027.json) contains the gate matrix and conservative cost calculation.

## Actual result

The original four-hour clock began at **20:07:32 UTC on 27 October**, with a fixed end of **00:07:32 UTC on 28 October**. The host and EIP reached verified safe state at approximately 20:16 UTC. There was one StartInstances request, one temporary EIP allocation and no controlled reboot. The original clock was never reset.

Fresh account/Free-plan/credit/ownership/root/CPU/SSH checks passed. One control table/namespace and one narrow role/profile were created; the profile is associated with the original host. Authority was initialized once and remains **stopped, generation 0, no leases, no command, no invitations issued**. These retained resources keep the existing review deadline of **23 December 2026, 18:00 UTC**. This is a review deadline, not permission for automatic deletion or extended retention.

The fixed guest shutdown guard was installed and verified before the relative 90-minute guard was retired. Metadata and endpoint-only egress units loaded successfully. The metadata dependency-failure/restore assertions and bounded log-rotation fixture completed before the later fixture failed. Actual role/network allow/deny probes, full application UID/capability inspection, protected provider enablement, signed readiness, reboot persistence and host capacity did not run to completion and remain unverified. Base installation is not application acceptance.

Cleanup disabled the application units, restored the safe relative guard and removed temporary TLS/hosts/deadline overrides. API observations verified the original host stopped, no public IP and zero EIPs for this operation. The watchdog exited after compute safety. No additional start is authorized by the completed one-Start proposal. Remaining acceptance assets must be inspected and adopted or removed by exact ownership/hash checks in any separately approved retry; do not blindly rerun the original base installer over them.

## Failure and corrections

The production logger correctly refuses a short write with `OSError("Incomplete lifecycle write")`, which has no numeric errno. The quota fixture expected only EFBIG/ENOSPC/EDQUOT, so it rejected that valid refusal. The unmodified frozen logger reproduced the same failure in a network-isolated Linux container. After correcting the fixture, its rotation, quota and lock cases all passed. No production logger/application change was needed.

The same offline correction retains bounded private subprocess stderr and serializes Decimal lifecycle timestamps as JSON numbers. The failed session's cleanup had reported an `activity:TypeError` while writing an optional receipt; API cleanup itself succeeded. A fresh read confirmed the actual authority remained stopped at generation 0, so no fabricated idle/drain transition was needed. The operation is now explicitly closed to ordinary work.

Before boot, a profile-name association refusal was reconciled by verifying the exact tagged profile and absent association, then using its verified ARN. A missing operator-adapter initializer method was reproduced and corrected using one conditional transaction. No table/profile was recreated, no Start was repeated, and neither issue changed the original deadline. Direct CLI import and Windows launcher ancestry checks were also corrected before boot. These preparation seams were missed initially; they are recorded rather than presented as host or account restrictions.

All **29 private operator regression tests** pass. The three exact frozen Linux log fixtures pass. The earlier full application regression remains **1,597 passed**, two upstream deprecation warnings. The application artifact is unchanged. Docker used for the offline reproduction was stopped afterward.

## Custody and cost

Exactly one existing-key status GET succeeded. The non-resetting USD 2 cap, exact 228 settlements, 19 legacy holds and conservative provider-gap accounting are preserved. The canonical ledger has its existing USD 0.10 readiness reserve and remains disabled on the protected PC. Old active local key paths remain retired, with protected recovery backups. Real provider key/ledger custody was never uploaded or enabled on the host. There were zero live model POSTs and no new provider allowance/top-up.

Using observed Start/stop and EIP allocation/release times, plus the full original DDB/storage/egress/KMS envelopes and 20% contingency, the conservative incremental bound is **USD 0.015806 of AWS credits**, below the approved USD 0.25 ceiling. This is an estimate while billing settles; cash remains USD 0 under the active Free plan. The previously approved retained 20-GiB root continues its separate storage charge. The tiny control table and IAM resources remain as approved.

Next is an offline preparation of a single bounded retry that reuses the retained table/profile and disabled canonical custody, verifies the remaining guest assets, and completes isolation, signed readiness, one reboot and capacity together. Another StartInstances request requires renewed authorization because the approved one-Start session has been consumed. Production-interpreter adoption and public wake/DNS/ACME/browser/live-provider activation remain closed.
