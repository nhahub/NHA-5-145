# CAP-07 continuation — 28 October 2026

Status: local investigation resumed; renewed cloud-session authorization pending.

## Evidence and remaining work

The second session is closed. Its single StartInstances was consumed; no guest
reboot occurred. The last recorded safe state is stopped, no public address,
and no operation EIP. This is a retained receipt, not a new AWS observation.

The private traceback reaches `guest.py:583`, the first `shell_python` call in
`barrier_probe`. That block creates the actual DynamoDB SDK client, reads the
permitted namespace, and checks denial for the other namespace. It failed before
the separate OpenRouter TCP-denial check. The traceback does not establish which
SDK operation failed or why. The underlying bounded command-error JSON remains
on the stopped root disk. Do not classify this as a provider/account failure.

No application source or frozen release has changed. No new AWS or provider
request was made during this local investigation. Real provider custody has not
been uploaded, and the local canonical ledger remains disabled.

## Proposed renewed session

Renew the existing consolidated CAP-07 execution scope for **one new session**,
starting within 48 hours of explicit approval. It does not reopen either closed
operation or reset their clocks, receipts, accounting, or authority identities.

- Up to **USD 0.25 additional existing AWS credits**, mandatory active Free plan
  and USD 0 cash. Retained-price planning bound is USD 0.142404 from the original
  proposal; refresh rates and account/credit coverage before any resource write.
  Abort if the refreshed conservative bound exceeds USD 0.25.
- Reuse the same stopped Stockholm t3.small, encrypted 20-GiB root, 1-GiB swap,
  DynamoDB table/namespace, and narrow role/profile. No helper, extra volume,
  resource replacement, authority initialization, or retention extension.
- One StartInstances, at most one controlled guest reboot after first-boot gates
  pass, and one temporary EIP. Four-hour absolute maximum from the first resource
  write, work ends by 160 minutes, normal stop/release by 180 minutes, independent
  fallback teardown at 210 minutes. No reboot after 135 minutes.
- Permit replacement of the stale SSH source with the freshly verified single
  operator IPv4/32. Keep ports 80/443 closed; no DNS, public ACME, or activation.
- Preserve the existing USD 0.10 readiness reserve, non-resetting USD 2 key cap,
  canonical UUID/history/uncertain holds and aggregate-gap accounting. No new
  reserve, top-up, key replacement, provider status GET, or live model POST.
- Preserve the original proposal's request, transfer, capacity and retention
  bounds. Existing root storage continues separately under its prior allocation;
  the table also retains its existing storage charges and review deadline.

## Execution order

1. Complete local preparation and synthetic operator checks. Create a new
   protected operation only after approval. Preserve both old operations intact.
2. Freshly verify account, Free plan, credit eligibility, retained identities,
   stopped host, root, SSH source/trust, CPU-credit constraints and disabled
   single-writer custody. Arm the independent stop/release watchdog before Start.
3. After SSH returns, **retrieve the existing root command-error JSON before
   reconciling or replacing any acceptance assets**. Use the existing protected
   SSH output mechanism; never echo raw diagnostics into chat. Limit retrieval
   to the eight newest root-owned regular `command-error-*.json` files under
   `/var/lib/shopping-copilot/acceptance-operator`, with no symlinks/hardlinks,
   at most 20 KiB per file and 160 KiB total. Do not read provider keys, ledger
   contents, environment files, or unrelated logs. If retrieval fails, stop.
4. Identify the exact failure. Correct only an evidenced acceptance-harness or
   already approved host-configuration defect, with a local failing regression
   followed by a passing check. Do not broaden IAM/network permissions, bypass
   a gate, or replace the frozen production release. If such a change is needed,
   preserve evidence and stop/release for offline preparation.
5. Reconcile the **second session's** profile UUID and asset hashes using the
   existing reconciler. Preserve prior archives and diagnostics. Retain the
   matching runtime/catalogue; do not rerun base package installers.
6. Complete the existing isolation and actual role/network-denial gates before
   custody upload or application activation. On any guest failure, attempt the
   same bounded diagnostic retrieval before teardown; retrieval failure must
   never suppress or indefinitely delay stop/release.
7. Complete protected custody/binding, signed readiness, one controlled reboot,
   persistence checks, and bounded private capacity lanes under the original
   acceptance criteria. No live model POSTs.
8. Disable application/canonical custody, preserve accounting and identities,
   restore the safe relative shutdown guard, stop the original instance and
   release the exact temporary EIP. Freshly observe stopped/no-public-IP/no-EIP;
   record any incomplete guest cleanup honestly. No automatic further retry.

Original criteria and rollback remain in
[the consolidated proposal](cap07-controlled-host-acceptance-proposal.md).
This document requests renewed execution authority; it is not evidence of cloud
execution or acceptance success.
