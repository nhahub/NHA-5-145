# Public operator preparation — 30 October 2026

The owner resumed, then reported only 21% model quota remaining. Cloud launch is
held to avoid exhausting quota during the bounded acceptance session. This is an
execution hold, not a new resource approval request or an owner-requested project
pause. The existing approved limits remain unchanged and unused.

## Verified progress

- Merged `origin/main` through `72dfce2` into the deployment branch at `7ffb62a`.
  Owner README/LICENSE additions and the successful CI fixture repair are
  preserved. No application runtime files changed relative to source `44e4952`.
- Native release and Lambda artifacts remain the previously verified source
  `44e4952` artifacts. The merge does not claim a new native build.
- All **55 private operator tests pass**. The **84 admission/lifecycle tests**
  also passed after the merge. Helper compilation and undefined/unused-name
  checks passed. These checks do not establish public or physical-phone results.
- Read-only AWS checks confirm active Free eligibility, the original host stopped
  without public IP, zero EIPs and zero Lambda functions. The public operation has
  zero starts, zero resource mutations, zero provider-status GETs and zero model
  POSTs. No cloud session clock or watchdog has started.

## Recovery safeguards implemented

An independent reviewer found three Important issues. Regression tests now cover
all three fixes: the controller initially has STOP-only permission and receives
one nonrenewable absolute START grant of at most 120 seconds; DNS-change intent
and rollback TTL are recorded before disclosing the address; and exceeding the
log threshold immediately requests cleanup. Actual lifecycle/executor tests cover
failed boots, uncertain dispatch, duplicate wakes, delay and expired permission.
The START grant is shorter than the 300-second failed-start recovery path. STOP
remains unconditional. There is no manual second-start fallback or grant renewal.

Additional tests cover partial-stage restoration before stop, diagnostics failures
that cannot prevent stop, uncertain CLI receipts, foreign-resource refusal,
partial CloudFront inventory, stale SSH-rule rotation, and distinguishing resource
deletion from final accounting. The public poweroff timer uses the absolute
session end plus a four-hour boot guard; it cannot preempt the real idle test with
the older 90-minute inspection limit. Finalization restores that inspection guard.

The retained canonical allowance had only its readiness allocation. The new
quiesced operator helper separately allocates the already-approved live USD0.10,
within the unchanged non-resetting USD2 key cap. It changes no ledger identity,
schema, old charge or uncertain hold. An idempotent root-owned intent journal
prevents duplicate allocation after a lost receipt. Finalization withdraws only
unused live allowance and preserves the original readiness reserve. Tests exercise
real SQLite history, interrupted receipts, four-attempt refusal and uncertain
holds. One independent provider-status GET is reserved on the host; it cannot be
retried and is part of the approved maximum five GETs. It has not been executed.

Read-only final inventory, actual EC2 caller/start-count verification, signed final
ledger checks and evidence-driven acceptance closure are implemented and tested.
They do not substitute for running them against AWS. No bare readiness flag can
replace signed application readiness, actual elapsed idle, physical-phone results
or preserved-accounting evidence.

## Resume frontier

Recover `.scratch/cap08-public-preparation/public-operation.txt`, then its
`quota-hold.json`, latest `local-preparation-snapshot-*`, source hashes and
`resume-frontier.md`. Private helper code is intentionally not in Git. The source
snapshot is an offline recovery record, not runtime per-request source pinning.
`local-ready.json` and `watchdog-ready.json` remain absent; do not fabricate them.

Before cloud launch, complete the final joined driver/failure rehearsal, including
manual-DNS and closure paths; refresh prices, account identity, eligibility, DNS
baseline and owner availability; then arm and verify the independent watchdog.
Only then begin the approved four-hour session. Existing source artifacts can be
reused while their exact hashes and selected runtime remain valid.

Public TLS/OAC checks, genuine invitation cold wake, desktop/physical Android,
the two live prompts, real 60-minute idle shutdown, final bookkeeping and actual
resource deletion remain unexecuted. Allow roughly two to three hours for the
cloud acceptance sequence; four hours is the absolute active limit. No Computer
Use or Brave access. All DNS creation/restoration remains owner-operated. Retained
disk/table storage continues to incur usage while the host is stopped.
