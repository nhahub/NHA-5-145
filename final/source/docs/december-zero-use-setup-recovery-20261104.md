# One-shot correction of a zero-use setup close

Operation: `1d4a59c9-c990-4589-8b29-d11a4fa9f3e1`.

AWS rejected the first schedule activation because its StartDate was more than
five minutes old after provisioning. The operator's conservative abort path
closed the operating marker with reason `owner`, fenced startup/controller access
and removed SSH ingress. This happened before any host Start, invitation issue,
provider status request or model POST. The private guard had not been invoked.

The existing approved design says the operating record is closed monotonically.
The requested exception is one audited correction of this operator-authored setup
close, after fresh inspection proves the operation has never been used. It is
not an automatic or deployed-runtime recovery mechanism.

The prepared private procedure:

- Requires the same policy/manifest and unexpired operating window, closed reason
  `owner`, zero start reservations and zero invitations, stopped lifecycle with
  no leases/command, and no prior correction audit. A guard-fault close, any used
  counter, an expired window or unknown custody refuses recovery.
- Uses one conditional DynamoDB transaction to record the complete prior closed
  state in an immutable audit row and correct only closed/reason/observed fields.
  It preserves the original identities, manifest, counters, lifecycle and history.
- Reuses the existing IP, bucket, three functions, four roles, distribution and
  dependencies. It updates the existing disabled tick and creates only the two
  remaining approved schedules in disabled state, proves the private guard without
  a scheduled invocation competing for its one concurrency slot, then enables all
  three schedules. Recurring StartDates use the next UTC minute at activation;
  all EndDates and the direct closing Stop target remain unchanged.
- Restores startup concurrency to one, creates the two remaining actionless
  alarms, verifies exact configurations/permissions, and requires a real private
  guard result of `open` before permitting the first maintenance Start.
- Permits one apply attempt. Ambiguous outcomes require inspection, not replay.
  Failure invokes the existing independent stop/fence and owned cleanup path.

No new resources beyond the original envelope, no additional EIP allocation,
budget increase, host starts, provider requests or code updates are authorized by
this correction itself. The original USD45 AWS-credit ceiling, Free plan/USD0
cash, first-write epoch and **4 December 2026,23:59 Cairo** closing time remain.
The initial two starts remain unused. The USD0.20/100 additional-attempt allowance,
two launch-smoke reservations, protected USD0.10 reserve and original non-resetting
USD2 key cap are unchanged. No counter, key, ledger or accounting reset is allowed.

The six synthetic recovery tests prove success retains identities/counters/history,
repetition is refused, and used, guard-fault or expired authority cannot reopen.
The deployed runtime and verified395b0b6 release are unchanged. The owner must
explicitly approve this narrow exception before its conditional transaction runs.
