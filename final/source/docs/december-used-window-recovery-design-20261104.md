# Consolidated used-window recovery design — 4 November 2026

## Evidence and the operator defect

The original operation remains `1d4a59c9-c990-4589-8b29-d11a4fa9f3e1`.
Maintenance, protected release/custody staging, all-authority DNS, trusted HTTPS,
five edge/access-refusal checks and an actual invited wake completed. The cloud
controller reported generation6 `ready` after its authenticated readiness check.

The separate readiness check from the operator PC returned false. That helper
has a two-second total deadline and deliberately hides the failure category.
The retained timings are consistent with that deadline, but do not establish
whether timeout, DNS, HTTP status or another condition caused this particular
miss. It must not be reported as a proven transport timeout or a passed local
signature check. No shopping request or model POST occurred.

The operator incorrectly treats every local acceptance failure as grounds for
terminal closure of the entire month-long operation and finalization of custody.
That coupling prevents an ordinary inspection/retry and has made setup recovery
brittle. A desktop command was also dispatched before the cold driver completed;
its prerequisite refused it before opening a browser or issuing shopping work.
Phase dependencies must be awaited and checked explicitly.

The safe abort ran. Fresh inspection proves the original host stopped, operating
and guard records closed with reason `owner`, two start reservations and one
issued invitation. The MAC-verified final guest receipt proves all249 attempts
unchanged, twenty old uncertain holds, zero new attempts/charges, disabled ledger,
and allowance reduced to accounted spending plus the protected USD0.10 reserve.
The same EIP remains owned; app/store DNS still points to it. No further boot or
reopening is authorized by either consumed zero-use correction.

## Proposed single recovery

Keep the same resources, operation identity, manifest, first-write time and
4 December23:59 Cairo close. Retain the two existing setup audits permanently.
Permit one additional, expressly owner-approved recovery of this now-used
owner-closed operation, preserving its two starts, one invitation and all history.
This is not a deployed automatic reopening mechanism.

Complete the local procedure and synthetic tests before its first cloud write:

1. Separate recoverable operator/transport verification failures from proven
   security, custody or spending failures. A recoverable local failure fences
   public startup and controller starts while diagnostics are retrieved inside
   the active bounded boot. It must not silently mark acceptance passed. A real
   invariant failure still invokes terminal closure and independent Stop.
2. Add a private operator readiness verifier with a bounded ten-second deadline,
   strict normal TLS/hostname validation, the same nonce/generation/release/HMAC
   checks and1024-byte response bound, and retained redacted failure category and
   elapsed time. Leave the deployed controller's two-second verifier unchanged.
   Require the cold driver to finish successfully before launching desktop work.
3. Inspect and audit the exact closed authority, owner-closed guard receipt,
   stopped lifecycle, first two audits and MAC-verified guest final receipt.
   Refuse a fault/budget/expired close, unknown custody, changed history or any
   new model attempt. Keep the recurring schedules disabled during the audited
   correction; keep the independent closing Stop active. Conditional writes must
   preserve all counters/policy fields and retain full previous records.
4. Allow at most **two additional launch starts**, making at most four for this
   initial acceptance and counting all four within the original100-dispatch
   lifetime maximum. First start is maintenance with the finalized application
   target disabled. Before altering custody, retrieve diagnostics and verify the
   protected on-disk ledger against the authenticated receipt, key/config/report
   digests and all249 original rows.
5. Permit one audited restoration of the unused USD0.20 public allowance from the
   final disabled custody state. Preserve every attempt, charge, uncertain hold,
   ledger UUID, existing allocation history and the original USD2 provider cap.
   Archive the previous final/boot/stop markers unchanged in protected storage;
   explicitly establish a new custody epoch for this recovery. Do not delete the
   audit history, reset the baseline, replace the key or increase any allowance.
   Restore the existing units/timer and qualification binding without changing
   the verified application release or model/provider configuration.
6. Reuse DNS, certificates, IP and edge controls. Stop maintenance, revoke the
   previous test invitation and issue one replacement while preserving cumulative
   invitation counts. Perform one actual invited cold wake, successful recorded
   signed verification, desktop acceptance within the original two launch-model
   reservations, genuine60-minute idle stop, signed accounting and handover.

The recovery application is one-shot. Ambiguous writes require inspection rather
than replay. If a real invariant failure occurs, stop/finalize/fence and report
the retained evidence; this proposal authorizes no further automatic recovery.

## Unchanged cost and resource bounds

**USD45 existing AWS credits total; Free plan/USD0 cash; original first-write and
December4 closing time; one existing EIP; original retained host/disk/table/profile;
same three functions/four roles/three schedules/distribution/bucket.** No additional
cloud resource, EIP allocation, Lambda code update, upgrade or paid DNS is proposed.
The existing eight-hour per-boot ceiling and independent closing Stop remain.

Model bounds remain USD0.20/100 additional attempts including at most two launch
smoke reservations, USD0.10 unexposed reserve, original non-resetting USD2 key cap,
and existing provider-status GET ceilings. Zero new attempts have been consumed.
No model request is permitted before signed readiness passes. All DNS-safe
cleanup requirements remain, including ownership plus authoritative absence and
the continuous7200-second cache interval before releasing the retained IP.

This requests approval of the consolidated recovery design and its exact exception
and start scope. Local implementation/tests must pass before execution. It does
not claim that this recovery is already implemented or that acceptance completed.
