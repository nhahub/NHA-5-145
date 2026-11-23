# Public Activation & Deployed Acceptance Proposal

29 October 2026. **Launch held for owner review. No cloud session has started.**

The owner approved the consolidated technical scope at `e98b2e9`, then requested
this launch review after the full regression result. That latest instruction
controls execution: do not use the earlier recorded grant to launch before this
review is complete. The remaining AWS credit activity is outside the current work.

## What this session will demonstrate

An invited tester opens the generated CloudFront HTTPS startup link, wakes the
existing Stockholm host and enters Shopping Copilot at `app.scpilot.tech`, with
the Controlled Storefront at `store.scpilot.tech`. Public certificates must be
trusted normally on desktop Chrome/Edge and the owner's Android Chrome. The
selected provider remains the current OpenRouter model; no Bedrock invocation or
provider switch is proposed.

Acceptance covers the actual public startup/IAM/OAC path, HTTPS/iframe and
invitation behavior, two bounded live shopping prompts, browser isolation and
refresh/SSE safety, and genuine automatic idle shutdown with all browsers closed.
Previously passed captured 1/5/8 host capacity remains separate from live-provider
latency. This session ends with teardown; it does not authorize a continuously
available demonstration for subsequent days or weeks.

## Verification and remaining preparation

- Private-host isolation, signed readiness, real reboot persistence and captured
  shopping capacity already passed CAP-07.
- The new optional absolute attempt ceiling is implemented through the existing
  durable ledger transaction. Focused verification passed88 tests, including
  concurrent clients/reconstruction, fifth-attempt refusal, invalid settings,
  qualified host propagation and in-memory tamper refusal. Two existing dependency
  deprecation warnings were reported.
- The full `agent/tests` plus `eval/tests` run completed with process exit0; the
  inspected final result is recorded below.
- Earlier public-path preparation passed72 tests and verified both Lambda ZIPs.
  Those artifacts predate the attempt-ceiling code; rebuild and independently
  verify the final native release and affected ZIPs before using them.
- Finish the protected execution runner and its ownership, partial-failure,
  deadline/cleanup and request-count tests before any AWS mutation. It has not
  been claimed ready or executed. Refresh account, exact prices, resource names,
  Free-plan service access and quotas before creation.

Full regression result: **1,617 passed, zero failures, two existing dependency
deprecation warnings in1,002.22seconds (16m42s)**; process exit0. The warnings are
from websockets/uvicorn compatibility imports. Python Ruff lint and formatting
checks pass across agent/eval/deploy; the independent runtime review found no
material issues. These results qualify the local code, not unexecuted public
deployment or physical-phone behavior.

## Explicit operating bounds for review

| Item                  | Proposed maximum                                                                                                                                                                                                                                                                                  |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AWS spending          | USD2 additional existing credits; active Free plan, USD0 cash, no upgrade.                                                                                                                                                                                                                        |
| Active session        | Four hours from first AWS write; at most two starts of the retained host, no reboot.                                                                                                                                                                                                              |
| Existing state        | Reuse the host, encrypted20GiB root, dedicated administration path, runtime role/profile and initialized DynamoDB authority; preserve generation/history and resident ledger/key custody.                                                                                                         |
| New resources         | One temporary EIP, one private S3 bucket, one generated-hostname CloudFront distribution, two OACs and one origin-request policy, two control Lambdas with dedicated roles/policies/log groups, one finite observation schedule/group/role, one completion metric and two action-disabled alarms. |
| Lambda bounds         | Each256MiB,30s handler timeout,512MiB temporary storage, reserved concurrency1; no VPC, layers or provisioned concurrency.                                                                                                                                                                        |
| Live provider         | At most four POSTs and USD0.10 additional OpenRouter usage inside the unchanged non-resetting USD2 key cap; existing readiness reserve preserved. Up to five status GETs, including the mandatory check before each POST. No automatic retries or new qualification set.                          |
| Inference enforcement | Pin the existing canonical attempt count+4 once in the protected operation and root-owned unit command. Do not recompute four fresh slots on restart. Refused/uncertain attempts consume their slots.                                                                                             |
| Traffic/storage       | At most1000 application HTTP requests,2000 startup-edge requests,1000 invocations per Lambda including ticks,240 ticks,1GiB public output,1GiB administrative transfer,100MiB new cloud logs and1GiB temporary S3 objects.                                                                        |
| Exposure              | Only app/store HTTPS and ACME HTTP ports80/443; SSH22 restricted to the freshly verified operator IPv4/32. No public application ports4000/8000, IPv6 ingress or anonymous Function URL.                                                                                                          |
| Cleanup tail          | Only disabled CloudFront dependency cleanup may extend to24hours; host stopped, startup access removed and EIP released within the active session. No further host/model activity; total AWS ceiling remainsUSD2.                                                                                 |

The detailed resource inventory, cost worksheet (~USD1.8614 with contingency at
its dated assumptions), request bounds, refusal criteria and rollback order remain
in [the consolidated proposal](cap-public-acceptance-proposal-20261029.md).
Refresh rates and validate its quantities before writes. These estimates and
operational thresholds are not enforceable AWS billing caps or bounds on hostile
traffic. Stop on account, access, cost or acceptance failures; no implicit increase
to any ceiling is authorized.

## Manual DNS boundary — owner instruction

**Do not use Computer Use or access Brave. The owner performs all DNS edits.**

The owner has confirmed no A records exist, and the supplied registrar screenshot
shows the A-record list empty. A read-only local DNS resolver check also returned
NXDOMAIN for app/store A, AAAA and CNAME queries. Refresh authoritative DNS at
execution; these observations do not establish future records or allocate an IP.
Any live desktop/phone steps requiring UI interaction will be owner-operated;
the operator uses permitted CLI/HTTP evidence and does not automate Brave or
work around the Computer Use restriction.

Before the first cloud write, the owner supplies the current app/store A-record
values and TTLs, or confirms they are absent. The operator prepares the exact
record instructions once the approved EIP is allocated; only the owner submits
them. No credentials, nameservers or unrelated records are requested or changed.

At the EIP binding step, provide two exact A-record instructions for `app` and
`store`, pointing to that same allocated IPv4, with TTL300 if supported. Confirm
authoritative DNS from CLI/network checks. A conflicting CNAME/AAAA or long prior
TTL that prevents bounded safe rollback blocks exposure; do not silently change
the topology. Do not allocate resources and let the clock run while waiting for
registrar access or an unprepared manual step.

For teardown, the owner restores the captured baseline or deletes only the new
app/store A records. Verify authoritative restoration and wait the recorded TTL
before releasing the EIP. Reserve enough of the four-hour window for this step.
The operator does not bypass this boundary by using a browser, registrar API or
another automation route.

## Ordered deployed checks

1. Finish local preparation and review; pin artifacts, approval, exact resource
   identities and rollback evidence. No production allowance/key reset.
2. Create disabled/private control resources; perform one inspect-first
   maintenance start. Reconcile owned test-only guest artifacts and session
   fences while retaining UID, metadata, capabilities, swap and log protections.
3. Bind manual DNS and qualify Caddy ACME/public origins with inference closed.
   Bind actual CloudFront/OAC/URL policies and verify signed readiness, uncached
   control responses and refusal paths. Never relax IAM or TLS to obtain a pass.
4. Stop maintenance, then cold-wake through a valid invitation and the genuine
   durable lifecycle claim. Do not use a manual second-start fallback.
5. Enable only the bounded qualified live allowance. Run the two predefined
   prompts and desktop/physical-phone checks. Any repair/advice POST counts
   against the same four-attempt maximum. Record incomplete cases honestly.
6. Close browsers, observe the real60-minute idle/drain/stop path using external
   observation, retrieve diagnostics before shutdown, then complete teardown.

Renew only the expired session interval of the binding against the same accepted
report/reconciliation, provider configuration, key digest and ledger identity.
The approved safety code change produces a new immutable release: record its
verified release fingerprint explicitly, never patch the old release or pretend
its old digest covers new bytes. Rebinding does not reset qualification evidence
or spending history. Any incompatible identity/evidence is a refusal, not a new
model qualification authorization.

## Final acceptance record

Report each public IAM/TLS/browser/live-provider/idle gate as passed, failed or
unverified, with actual evidence. Revoke test invitations, preserve latest canonical
accounting and unknown outcomes, settle lifecycle bookkeeping, stop the host,
close public ingress and verify no EIP remains. Delete all new owned resources
and independently inventory them. Explicitly report any disabled-edge cleanup
dependency still pending; do not report clean teardown prematurely.

The retained original disk/table continue their previously approved storage usage.
No additional retention window, public availability promise, merge or push is
implied by approving this bounded acceptance launch.
