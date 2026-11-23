# CAP-06 CloudFront/Lambda access bundle

Continue the owner-selected Stockholm automatic-wake design with offline access
configuration and a viewer signing fix. No resource creation, account login,
permission simulation against AWS, paid call, DNS change or certificate request.
Bedrock, public IPv4 credit eligibility and all deployment acceptance gates stay
open. The owner must still approve the complete resource/cost/rollback inventory.

## Builder decisions within the selected topology

Create a pure Python `deploy/cloud_access.py` renderer taking a frozen
`CloudAccessBindings(account, instance, table, namespace, distribution, startup,
controller, bucket)`. All values are trusted deployment inputs, never browser
fields. Require exact bounded identifiers without wildcards or ARN interpolation:
12-digit account; modern 17-hex EC2 ID; bounded DynamoDB table and namespace;
CloudFront E-prefixed uppercase distribution ID; distinct bounded Lambda names;
valid single-label general-purpose S3 bucket (no dots, wildcard/path, IPv4 or
reserved service prefixes/suffixes). The region and partition are fixed to
eu-north-1/aws. No actual identifiers
are selected or discovered by this slice.

`render_cloud_access(bindings)` returns a deterministic JSON-serializable bundle:

- Separate startup/controller role trust and permissions. Startup has no EC2
  permissions; it can invoke only the exact controller function for future async
  wiring. Controller can StartInstances/StopInstances only the exact instance;
  DescribeInstances requires Resource \* with a Stockholm region condition.
- DynamoDB reads: GetItem only, exact table and partition namespace. Transaction
  writes: PutItem, UpdateItem and ConditionCheckItem only, same table/partition,
  restricted to TransactWriteItems enclosing operations. No DeleteItem, Scan,
  initialization Query, table creation or nonexistent TransactWriteItems IAM
  action. LeadingKeys uses ForAllValues:StringEquals plus Null:false. Runtime
  principals are trusted application identities; IAM does not prove protocol
  semantics or prevent all table-attribute abuse by compromised runtime code.
- Only CreateLogStream/PutLogEvents for each role's own precreated Lambda log
  group streams. No CreateLogGroup, log reads or retention administration. List
  the two precreated log groups with seven-day retention in the handoff bundle.
  Do not enable invocation/event/body logging.
- Lambda Function URL AuthType AWS_IAM and CloudFront resource policy statements
  for BOTH InvokeFunctionUrl and InvokeFunction, exact function and distribution
  ARN, cloudfront.amazonaws.com principal. Restrict the former to AWS_IAM and
  the latter to InvokedViaFunctionUrl=true. Do not add undocumented SourceAccount
  context requirements or an anonymous Function URL policy.
- S3 OAC policy grants only GetObject below waiting/ for that exact distribution.
  No public website access or release/catalogue-backup access through CloudFront.
- OAC configs for lambda and s3: always sign, sigv4. Custom origin request policy
  forwards only origin, content-type and x-amz-content-sha256; no cookies or query
  strings. CloudFront supplies the origin Host; do not forward viewer Host or
  Authorization. Disable control caching using AWS's managed CachingDisabled
  policy and zero error-caching TTL for supported error status codes. POST needs
  all seven CloudFront AllowedMethods; the application still refuses unsupported
  routes/methods. Never cache startup/control responses.

This is an access bundle, not a complete CloudFormation stack or deploy command.
It creates no SDK clients and reads no environment/profile/credentials. Do not
package it as a deployable template with dummy handlers or fake resources.
CloudFront generated-host binding, Lambda code packaging, role attachment,
initialization, controller scheduling, fixed instance binding, edge cost bounds
and actual AWS policy/resource qualification remain explicit deployment work.

## Viewer POST body

The existing waiting page computes SHA-256 of the exact UTF-8 JSON body with
Web Crypto, then sends lowercase hexadecimal x-amz-content-sha256 with that same
body. No code/header logging, URL/storage use, extra request or external library.
Hash failure must stop before fetch and show the existing generic failure text.
Use the same behavior in the loopback rehearsal and generated HTTPS page.

Origin forwarding is a prerequisite for the handler's exact-Origin check, not an
alternative to AWS_IAM/OAC. A body digest is not invitation authentication.
Production's allowed origin must be bound to its actual generated hostname before
exposure; this bundle must not invent one or make the handler trust arbitrary Host.

## Verification

Offline assertions pin permissions, resources, conditions, unsafe-input rejection,
determinism, exact OAC signing and header/caching settings. A headless browser
intercepts every request locally at a synthetic secure HTTPS origin; verify the
actual POST body digest with Python hashlib, no code in URL/storage, input cleared,
ready link preserved and no fetch when hashing fails. No request reaches AWS.
Re-run local waiting HTTP/lifecycle tests, remote startup/controller tests and a
fresh release packaging check; repository lint/format and independent review.

Primary AWS findings live in
docs/research/2026-10-22-cap06-lambda-oac-contract.md. Cloud IAM simulation and real
POST/OAC access tests still require the approved deployment. Extra controller
invocations must enter the final cost estimate; this slice changes no allowance.
