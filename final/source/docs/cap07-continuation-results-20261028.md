# CAP-07 continuation results — 28 October 2026

**Private acceptance remains incomplete. Compute teardown is verified safe.**

Update: the normal off-host bookkeeping subsequently completed cleanly at
14:40:46UTC on28October, stopped/generation1. The owner-authorized focused
continuation is recorded separately in
[the focused results](cap07-focused-results-20261028.md). Later references below
to pending bookkeeping describe the original report time.

The owner explicitly renewed the bounded session in
[the continuation proposal](cap07-continuation-20261028.md). It reused the original
Stockholm host, root, role/profile and DynamoDB identities. No new control resource,
public activation, provider status GET or live model POST occurred.

## Actual host evidence

- T0: 13:32:01 UTC; unchanged absolute end: 17:32:01 UTC. One StartInstances,
  one controlled guest reboot and one temporary EIP were used. Stopped/no-public-IP/
  EIP-released receipt: 13:41:08 UTC. Fresh subsequent safety observations agree;
  guest and API teardown returned no errors.
- Retained root diagnostics were retrieved before asset reconciliation. They show
  DynamoDB EndpointConnectionError with connection refused. The retained firewall
  allowed `35.71.98.100`; the host subsequently resolved the endpoint to
  `35.71.98.101`. Base installation already resolved on the host, but subsequent
  DNS lookups could rotate. A temporary hosts mapping now pins the exact verified
  endpoint set used by the firewall; TLS hostname/certificate validation and
  namespace restrictions are preserved. Cleanup removes only its owned block.
- Actual allowed-namespace read, other-namespace denial and OpenRouter TCP denial
  all passed after the correction. Metadata dependency-failure/restore and all
  three log fixtures passed.
- Protected real custody and qualification binding installed successfully.
  Signed readiness passed; wrong key/generation, stale response and unsigned
  response were refused. First-boot service UID/capability/resource isolation,
  metadata denial and positive Agent metadata access passed.
- A distinct boot ID and automatic application recovery were observed after the
  controlled reboot. Swap, firewall rules, service units and signed readiness
  passed without manual start/restart or persistence repair.
- Actual control lane passed at 1/5/8 clients: 126 ingress requests, zero model
  POSTs, minimum available memory 1,544,470,528 bytes, maximum swap used zero.
- Capture namespace isolation passed: the synthetic service could not open real
  provider custody. The captured lane then aborted on its first capacity sample
  because the expected capture service cgroup was absent. That sample had
  1,614,364,672 bytes available memory, zero swap/OOM, and a positive CPU-credit
  floor. It does not establish a hardware-capacity failure. The driver stderr was
  empty and no captured shopping result was produced. **Do not mark this lane
  passed or the whole private-host gate complete.**

## Offline correction and verification

The exact capture binding-construction code was executed under Linux with
umask022 against the frozen protected-file reader. It created `binding.json` as
0644 and was refused with `Private file required`. Explicit chmod0400 corrected
the fixture; the identical Linux probe then passed. Production validation and
the frozen application release were unchanged. The actual failed guest's file
mode/startup traceback was not recovered before shutdown; another actual-host
test must confirm whether this resolves the complete captured-lane failure.

The complete native Python3.12.14 TLS/HTTP/SSE rehearsal was rerun using the exact
corrected operator binding code under umask022 and synthetic custody/authority.
Both lanes passed: control126 and captured140 ingress requests; captured cohorts
1/5/8 completed1/5/5 with three expected busy refusals at8. Twenty-two fake model
POSTs, zero real AWS/model calls. Existing uncertainty was preserved. This is
local native evidence, not a replacement for the missing host result.

Thirty-seven private operator regressions pass. The original application-wide
1,597-test receipt remains historical; application bytes did not change, so it
was not rerun for these operator-only corrections.

## Final custody and lifecycle

Applications and host canonical custody were disabled during successful guest
cleanup; a protected final ledger backup remains on the retained root. The PC
canonical ledger remains disabled. The non-resetting USD2 cap, existing USD0.10
reserve, UUID, settlements, uncertain holds and aggregate-gap accounting remain
in force. Do not overwrite the guest ledger from an older PC copy on a future
attempt; reconcile the guest backup first.

At the fresh teardown observation, lifecycle generation1 was `unhealthy` and
non-admitting. Invitation revocation and teardown completed without errors. The
normal lifecycle requires a real 3,600-second idle interval plus draining; its
earliest completion is approximately **14:39:40 UTC**, followed by bounded SDK
operations. A finite local worker waits without cloud polling, then attempts
normal off-host reconciliation inside the original17:32:01UTC deadline. It cannot
start compute and stops on a pause marker. Its protected receipts are
`authority-finish-wait.json`, then either `authority-finish-complete.json` or
`authority-finish-error.json`. **Completion was still pending when this report
was prepared; verify the receipt before claiming authority stopped.**

Both old grants remain closed. This renewal's Start and reboot are consumed;
no automatic retry or extra boot is authorized. Future preparation must account
for retained real custody, capture assets and lifecycle generation1. The older
empty-custody reconciler and generation0 assumptions must not be reused blindly.

## Credits and next gate

Official EC2/gp3/IPv4/DynamoDB rates were refreshed on28October with no increase.
Rounding the running/IP interval up to ten minutes and retaining the full prior
request/storage/egress/KMS envelope plus20percent contingency gives a conservative
incremental bound of **USD0.020044 credits**, not a final billing measurement.
Free plan and USD0cash were freshly verified. The existing root-storage
allocation remains separate; retained disk/table storage charges continue.

Remaining CAP-07 work: verify final authority receipt, prepare a custody-aware,
generation-aware continuation offline, then obtain a renewed exact cloud grant
for the actual captured-lane retest and safe teardown. Public deployment remains
separately gated. No push or merge was performed.
