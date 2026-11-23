# Request-context setup continuation — 4 November 2026

Operation: `1d4a59c9-c990-4589-8b29-d11a4fa9f3e1`.

The approved schedule-date correction ran once and recorded its immutable audit.
It created the remaining two disabled schedules and two actionless alarms, then
aborted at the operator's IAM simulation. That request omitted
`aws:RequestedRegion`; the account's regional policy therefore made the simulation
report a denial. Fresh read-only simulation with the actual `eu-north-1` context
allows both independent Stop roles and denies guard Start. No IAM change is needed.
The abort path closed the operating marker again with reason `owner`.

The first one-shot exception has been consumed. This proposal requests exactly
one additional, separately audited correction of that unused setup close. It
does not authorize automatic reopening or change the deployed runtime.

Fresh read-only inspection at approximately 22:36 Cairo confirms:

- The original host is stopped, with zero start reservations, invitations,
  provider requests or model POSTs. The private guard's persisted seed is intact
  and has never executed. CloudFront is disabled, startup concurrency is zero,
  the controller is Stop-only, and the dedicated security group has no ingress.
- All three exact schedules already exist and are disabled. Both exact
  actionless alarms exist and carry this operation's ownership tag.
- The original manifest, identities, first-write epoch, closing date and release
  remain unchanged. The account is ACTIVE/FREE with USD179.30 credits reported.
- A real Lambda `DryRun` returned HTTP204 and executed no function, verifying the
  corrected explicit CLI arguments before a live guard invocation.

The prepared procedure first repeats these read-only checks and the context-aware
permission checks. Only with explicit approval does one conditional DynamoDB
transaction correct `closed`, `reason` and `observed`, while recording the full
previous row at `operating-recovery#request-context-v1`. It requires the original
`operating-recovery#schedule-activation-v1` audit, preserves it byte-for-byte in
meaning, and refuses a prior continuation, any used counter, guard fault, expired
window, lifecycle lease/command, changed configuration or uncertain guard custody.
The transaction checks the first audit and lifecycle revision against races.

It then restores startup concurrency to one and invokes the real private guard
once, while all schedules remain disabled. Only an actual `open` result permits
enabling the three existing schedules, with fresh next-minute recurring StartDates.
All EndDates and the independent closing Stop remain unchanged. No schedule,
alarm, IP, role, function or other resource is created or replaced. No IAM policy
or Lambda code change is needed. Failure after the correction retains diagnostics
before the existing independent Stop/fence path; an inspection failure makes no
mutation. Ambiguous outcomes are inspected rather than replayed.

The original **USD45 AWS-credit ceiling, Free plan/USD0 cash, 4 December 2026
23:59 Cairo closing time, and original first-write epoch** remain unchanged.
The initial two host starts are still unused. This correction itself starts no
host and sends no provider request. Subsequent maintenance and acceptance remain
subject to the existing approved design: USD0.20/100 additional model attempts,
two launch-smoke reservations, protected USD0.10 reserve and the original
non-resetting USD2 key cap. No identity, counter, key, ledger or hold is reset.

All 52 private operator, custody, provisioning, rollback and recovery checks pass.
The new cases were observed failing before implementation. They cover preservation
of the first audit/history/policy, repeat refusal, missing or altered prior audit,
used start/invitation counters, fault closure, expiry, and the real Stockholm
context in the joined AWS-model provisioning check. The verified runtime395b0b6
and its full regression evidence are unchanged; deployed guard proof is still
required before the first host start.

Approval is required because the approved design says the operating record closes
monotonically, and the previous exception allowed only one apply attempt.
