# Final bounded desktop setup recovery — 3 November 2026

Cold wake and signed generation4 readiness pass; controller IAM is STOP-only.
Two desktop setup attempts made zero model submissions. Both failed before the
shopping task: the driver clicked before the deferred cart handler hydrated.
The second native form submission returned409 invalid_or_stale_cart_edit. A
GET-only real HTTPS browser diagnostic shows all16resources load200, no script
errors, and cartRevision0 after load. This identifies the missing driver wait;
the previous post-click wait alone was insufficient.

Prepared correction waits for html data-cart-revision0 before selecting/clicking,
then waits for the explicit confirmed cart result before navigating. Preserve
both failures/screenshots/logs and all request/model/start counters. Permit one
final setup retry only when the latest retained receipt shows zero submissions;
reserve a separate one-shot flag, never reset prior attempt flags.

Both original admission redemptions have been consumed. Request permission to
revoke the current desktop invitation, retain its history, and issue exactly one
replacement desktop invitation with one redemption/two sessions. At most one
active desktop invitation; archive the original protected code record. No key,
ledger, allowance or lifecycle reset. Refuse any further setup replay.

Replacement issuance must occur before00:59:17Cairo today (22:59:17UTC2November,
original first-write plus90minutes), and the driver must start before that same
time and close before01:04:17Cairo (plus95minutes). Replacement expiry remains
01:09:17Cairo (plus100minutes). If these bounds cannot be met, retrieve diagnostics
and tear down; do not shorten or fabricate the60minute idle proof.

Same USD2 AWS-credit ceiling, Free/USD0cash, same running host/EIP/table/resources,
zero additional host starts or code updates. Maximum4modelPOSTs/USD0.10 and5status
GETs within the original nonresetUSD2 cap/readiness reserve remain unchanged;
all previous model submission counts are zero. Global application/edge request
ceilings remain1000/2000 and include both failures plus diagnostic requests.
Original160minute supervisor cutoff02:09:17Cairo, four-hour compute/control end
03:29:17Cairo and six-hour EIP-only end05:29:17Cairo remain unchanged. Owner's
closed-tabs confirmation remains in force. DNS/HTTPS stays healthy during idle,
then owner-only DNS removal, actual7200s TTL wait, EIP release and full teardown.

Approval is requested because this replaces a consumed admission credential and
moves its issuance cutoff by five minutes; the existing exact acceptance bounds
must not be silently reset under the project's operating rules. This is not a new cloud session or
additional financial allocation. Private checks cover one-shot zero-model recovery.
