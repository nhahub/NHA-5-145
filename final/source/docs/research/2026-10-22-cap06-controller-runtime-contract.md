# CAP-06 controller runtime contract: offline preparation

Checked 22 October 2026 against primary AWS documentation using agent-reach Exa
search and the dedicated web reader. No AWS account calls, resource changes,
credential inspection, remote writes or runtime activation occurred. These facts
support an injected controller seam; deployed scheduling, account feasibility,
cloud acceptance and the existing CAP-05 model gate remain unresolved.

## Asynchronous handoff

Use the Lambda Invoke API with `InvocationType="Event"` and the exact configured
worker function ARN/qualifier. A successful API response has `StatusCode=202`;
the API status does not report function execution errors. This operation needs
`lambda:InvokeFunction`, distinct from the Function URL invocation grant. Keep
the permission restricted to the intended worker; a URL-only
`InvokedViaFunctionUrl` grant does not authorize direct Invoke API calls.
[Invoke API](https://docs.aws.amazon.com/lambda/latest/api/API_Invoke.html).

Lambda places asynchronous events into its own internal queue and returns before
the function runs. Therefore 202 establishes accepted handoff, not worker
completion, an EC2 command, host readiness, or successful shopping access.
The caller must not interpret acceptance as any of those outcomes.
[Asynchronous invocation](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async.html).

`MaximumRetryAttempts=0` means no additional retries **when the function returns
an error**. `MaximumEventAgeInSeconds` accepts 60–21600 seconds: the service cannot
be configured with a five-second queue age. Scope the EventInvokeConfig to the
same version/alias actually invoked; CloudFormation requires its `Qualifier`.
[EventInvokeConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lambda-eventinvokeconfig.html).

These settings do not establish exactly-once delivery. AWS separately documents
requeueing after throttling/system errors and possible duplicate delivery even
when execution reports no error. Queue load can delay delivery or events can age
out. Thus disabling function-error retries does not remove the need for durable
duplicate rejection and fresh deadline/authority validation at execution.
[Asynchronous error handling](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html).

Keep application/SDK requests single-attempt. Botocore
`retries={"total_max_attempts": 1}` includes the initial request and disables SDK
retries. It takes precedence over `max_attempts`; connect/read timeouts remain
separate configuration. A lost/malformed Invoke response is an uncertain handoff,
not evidence that no worker will run. Do not automatically invoke again.
[Botocore Config](https://docs.aws.amazon.com/botocore/latest/reference/config.html).

## Concurrency and dispatch authority

`ReservedConcurrentExecutions=1` limits this function to one concurrent execution
and reserves that capacity. It does not preinitialize the runtime. Reserved
concurrency is function scoped, not a durable event identity or command lock.
AWS also requires capacity for 100 unreserved executions, so the account's actual
quota must be qualified before treating this setting as available.
[Reserved concurrency](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html).

Design consequence: serial execution can reduce contention, but successive
duplicates still execute and other trusted processes may touch the same
lifecycle. Preserve the persistent command claim, no takeover/replay after an
uncertain dispatch, fresh generation/revision/deadline checks, and at most one
EC2 command attempt per claimed command. Do not claim that concurrency or a
DynamoDB generation fences an already-sent EC2 request. A queued event should
carry bounded references, not become independent authority to start the host.

An HTTP poll or host heartbeat may trigger one bounded controller pass, and an
internal invocation may hand off one pass. No pass should sleep, loop waiting
for readiness, self-invoke recursively, or silently install a scheduler. The
selected inventory has no approved EventBridge or SQS resource; AWS's internal
async queue is not a project-provisioned SQS queue. Liveness while there are no
polls/heartbeats remains a deployment/scheduling acceptance gate. These are
project design constraints, not promises made by the Lambda service.

## Exact-instance observation

Call `describe_instances(InstanceIds=[configured_instance_id])`, never an
unfiltered account inventory query or a caller-supplied instance selection.
AWS returns only specified IDs, may omit unowned instances, and errors for
invalid IDs. Do not combine `MaxResults` with InstanceIds. EC2 is eventually
consistent and response ordering is unspecified; a new observation is not an
atomic fence over a concurrent command.
[DescribeInstances API](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeInstances.html).

The SDK response nests `Reservations` then `Instances`, with `InstanceId` and
`State` (`Code`, `Name`). Validate the response metadata, collection types,
exactly one matching configured instance, state pair and absence of an
unexpected continuation token before recording a trusted observation. Empty,
duplicate, extra-instance, malformed, service-error and timeout outcomes must
fail closed. This strict response acceptance is a project choice over the AWS
response schema; do not take the first returned item on faith.
[Boto3 describe_instances](https://docs.aws.amazon.com/boto3/latest/reference/services/ec2/client/describe_instances.html).

EC2 state codes are unsigned 16-bit integers with an internal high byte that AWS
says to ignore. Validate an actual integer (not bool), range 0–65535, then match
`Code & 255` with Name:

| Low byte | Name          |
| -------- | ------------- |
| 0        | pending       |
| 16       | running       |
| 32       | shutting-down |
| 48       | terminated    |
| 64       | stopping      |
| 80       | stopped       |

[InstanceState](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_InstanceState.html).

Map only lifecycle-supported states into trusted lifecycle observations.
Shutting-down/terminated are not stopped and must not authorize a restart.
Running alone does not prove application health: readiness still needs the
separate configured trusted health observation. The existing
`agent/lifecycle/executor.py` acknowledgement check compares raw Code to the
low-byte constants; legitimate nonzero high bits would conservatively make it
uncertain. A future change should normalize according to the documented rule
and preserve malformed-state rejection, with regression coverage.

## Focused offline evidence for the next slice

Verify exact Event invocation and one SDK call; reject non-202/malformed/lost
handoff responses without retry; duplicate/stale worker events cannot dispatch
the same claimed command again; no worker sleep or self-chain; fixed Stockholm
endpoint/instance selection; all six state pairs including nonzero high bytes;
bool/out-of-range/mismatched codes; empty/duplicate/extra-instance/continuation
responses; and running-but-unhealthy observation. Stubbed tests establish local
behavior only. Deployed IAM, async delivery, actual concurrency, observation
trust, scheduling liveness, cost bounds and cloud recovery still require their
authorized acceptance evidence.
