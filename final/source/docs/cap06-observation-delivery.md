# CAP-06 inactive external observation preparation

22 October 2026. A browser-independent observation pass and a pure disabled
resource bundle are prepared locally. No AWS schedule, role, alarm, policy,
runtime configuration or selected inventory has been created/changed. The
[design](specs/2026-10-22-cap06-observation-delivery-design.md) is a
conditional service proposal; actual adoption/apply requires full cost/resource/
rollback review. See the [primary-source research and rate assumptions](research/2026-10-22-cap06-observation-delivery-contract.md).

## Prepared runtime behavior

The existing controller accepts exactly `{"kind":"tick"}` on its internal
Lambda invocation path. Startup HTTP cannot forward a caller-selected tick,
host, operation or generation. A tick reads the bound current lifecycle. Stopped
state takes three strong datastore reads, no write and no EC2 call. Otherwise
it captures a fresh generation/revision observation, reconciles health/deadline/
leases/activity/drain, and attempts at most one already-pending command.

A valid accepted wake whose dispatch notification was lost can progress without
a browser. START still needs the existing fresh invitation/window/deadline claim
and pre-call checks. No tick creates a wake or repeats a consumed/uncertain claim.
Readiness and stop completion require later observations, not EC2 acknowledgement.
Existing strict generation-bound dispatch/observe behavior remains unchanged.

Only a successful trusted tick emits one bounded JSON EMF `TickCompleted` count
in namespace `ShoppingCopilot/Lifecycle`, fixed `Component=Controller`. This
dimension is for this one-controller deployment; multiple independently named
controllers would need a separately reviewed unique dimension/alarm binding.
There is no event, generation, code, key or request identifier in the log.
EMF processing is asynchronous and may duplicate values; it is an availability
signal, not a command ledger. Browser-triggered calls never emit this metric.

Tick initialization, runtime, authority or metric-output failures escape both
runtime and lazy entry as `RuntimeError("Scheduled observation unavailable")`,
without original exception details, so Lambda can count Errors. Failed entry
initialization stays latched; it is not retried on later invocations. Ordinary
controller events keep generic unavailable results. A failing tick can leave a
claimed command unresolved; the existing deliberate owner-investigation fence
continues to apply.

## Disabled configuration documents

`deploy.observation.ObservationBindings` binds account, controller, dedicated
group, schedule, execution-role name and UTC whole-minute start/end datetimes.
`render_observation` revalidates them and returns documents only. Dates span
1 minute through 60 days; the deployment owner must separately ensure they are
future dates within the approved demonstration/teardown window.

The bundle contains the dedicated schedule group, execution-role trust scoped
to exact account/group ARN and an invoke-only controller policy. The one-minute
schedule is always **DISABLED**, flexible window OFF, fixed tick input, delivery
retry0/age60, completion deletion NONE. Proposed controller settings are256MiB,
timeout30seconds, reserved concurrency1 and async function-error retries0/age60.
These are reviewable inputs, not evidence of account quota or runtime sufficiency.
Dates are serialized UTC strings; this is not a deployable stack or direct apply API.

Two standard-resolution alarms have **ActionsEnabled=false** and no action ARNs:
controller Errors at least1 in any of5one-minute periods, and TickCompleted
below1/missing in all5one-minute periods. Owner console review remains necessary;
there is no email/SNS notification. No additional PutMetricData runtime grant is
needed for EMF, but log delivery/custom metric charges and deployed extraction/
alarm behavior require qualification. Do not enable the schedule before the
actual target, policies, configuration, keys, metrics and stop procedure pass.

## Operation profile and evidence boundary

The offline Moto/Stubber profile records intercepted API calls and conservative
DynamoDB-JSON item byte sizes; it does not measure AWS billing or latency.

| Pass                           | Strong gets | Transactions | Largest observed item JSON |
| ------------------------------ | ----------: | -----------: | -------------------------: |
| Stopped                        |           3 |            0 |                  418 bytes |
| Unclaimed accepted START       |          26 |            3 |                  634 bytes |
| Ready with128live work leases  |          15 |            1 |                6,868 bytes |
| Begin idle drain               |          15 |            1 |                  470 bytes |
| Dispatch pending STOP          |          21 |            3 |                  638 bytes |
| Uncertain command, no takeover |          15 |            1 |                  629 bytes |

Cold runtime construction adds four metadata gets. These fixture results fit the
proposed36-get/4-transaction/16KiB assumptions but do not establish universal
maxima or real consumed-capacity accounting. Actual deployment still needs
measured item/condition counts and total durations, including INIT and duplicates.
The research's conservative86,400tick60-day stress scenario is USD22.18, rounded
to proposedUSD23 credit allocation. Prior55.50reference plus23=78.50; only1.50
remains inside proposed80, with the prior20separate reserve. No inference/spend
authorization or cash safety claim follows from arithmetic.

Tests exercise stopped no-write/no-command, lost-notification recovery, duplicates
and concurrent claims, revocation/expiry/deadlines, late-start cleanup, unknown
claims, activity/probe races, live and expired work leases, closed-browser drain/
stop, redacted entry/runtime failures, tick-only telemetry and disabled narrow
configuration. They make no real AWS/model requests. Rebuilt artifact evidence
and full regression results are recorded in the checkpoint and evidence file.
Final affected suite passed1,036tests, including a fresh release build;
independent review found no issues and passed108focused cases. See
[the evidence record](../eval/evidence/cap06-observation-delivery-20261022.json).

Actual service/credit/concurrency eligibility, finite activation dates, reliable
delivery under backlog, Linux memory/runtime behavior, IAM/OAC, public TLS,
account/budget gates and closed-browser cloud acceptance remain required.
Scheduler/queue outages can delay observations; roughly60–63minute idle stop is
an assumption for healthy delivery, not a guarantee. Keep owner investigation/
manual stop, drain before schedule end and disable schedule before teardown.
Bedrock quota/qualification and all Free-plan/Stockholm/zero-cash gates stay open.
