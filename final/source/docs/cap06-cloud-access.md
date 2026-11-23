# CAP-06 prepared CloudFront and Lambda access controls

22 October 2026. Offline preparation only: no resources, IAM changes, AWS policy
simulation, Function URL, distribution, DNS or certificate request has been made.
The Bedrock quota blocker and all deployment gates remain open.

## Reviewable access bundle

`deploy/cloud_access.py` exposes frozen `CloudAccessBindings` and
`render_cloud_access`. Supply exact owner-controlled account, instance, table,
namespace, distribution, startup/controller function names and bucket identifiers.
The renderer returns JSON documents; it creates no SDK client, reads no profile
or environment and offers no deploy command. No actual identifier is chosen or
discovered by this preparation. The emitted sections are not a CloudFormation
stack and cannot be treated as a finished deployment.

| Boundary                  | Prepared scope                                                                                                                                         |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Startup execution role    | Exact table/namespace, own log streams and invocation of the exact controller; no EC2 permissions                                                      |
| Controller execution role | Exact table/namespace, own logs and start/stop of one instance; region-bound DescribeInstances requires Resource \*                                    |
| DynamoDB runtime          | GetItem and transactional PutItem/UpdateItem/ConditionCheckItem; no Query, Scan, DeleteItem or table/initializer permissions                           |
| Function URL              | AWS_IAM plus both InvokeFunctionUrl and InvokeFunction grants to CloudFront; exact distribution ARN and appropriate URL-only conditions                |
| Private S3 origin         | CloudFront GetObject below waiting/ only; no release/catalogue-backup reads through this grant                                                         |
| CloudFront control        | Always-sign sigv4 OAC, HTTPS viewers, disabled caching, zero error-cache TTLs, origin/content-type/body-hash allowlist, no cookies or query forwarding |
| Logs                      | Precreated separate function log groups, seven-day retention, runtime stream/write only; no event/body logging                                         |

The DynamoDB transaction request is not an IAM action named TransactWriteItems:
IAM evaluates the constituent actions, restricted by EnclosingOperation. The
partition condition does not separate all application methods sharing that
namespace or prove lifecycle safety; the runtime still enforces that protocol.
Initializer/admin permissions must remain separate.

CloudFront requires all seven allowed HTTP methods to forward POST. The handler
still rejects unsupported method/path combinations. The origin request policy
does not forward viewer Host or Authorization; CloudFront supplies origin Host,
its signature and other protocol headers. Its allowlist is not a claim that the
Lambda event contains only three headers. Cookies and query parameters are
discarded at the edge; they never supply shopping/wake authority.

## Browser POST signing

The shared waiting page hashes the exact JSON string with Web Crypto SHA-256,
then sends that same UTF-8 body with x-amz-content-sha256. AWS requires this
payload digest for viewer POST/PUT through Lambda OAC. A failed hash sends no
wake request. The field is already cleared, and no code/digest is logged or stored
in a URL, localStorage or sessionStorage. The digest is not an invitation or an
AWS credential. The same behavior works on HTTPS and trusted localhost contexts.

Transport IAM/OAC and exact configured Origin are independent requirements. Never
fix an access failure by making the Function URL anonymous or trusting arbitrary
Host headers. Bind the actual generated CloudFront hostname before exposure. The
startup page still links only to the fixed shopping destination and asks for code
re-entry; wake authority does not authorize a shopping Action.

## Remaining deployment work

The [explicit runtime factories and authenticated observer](cap06-controller-runtime.md)
are now prepared offline. Their bootstrap/package, scheduling, fixed host wiring
and async Agent work leases are not activated.
Role attachment, private REST bucket ownership/Block Public Access, HTTPS origin
settings and timeouts, initialized remote identities, concurrency/error handling,
edge cost containment, public TLS and Android/desktop acceptance remain required.
The final estimate must count controller invocations and DynamoDB operations;
this preparation increases no allowance and establishes no billing ceiling.

An independent review and offline tests can check document scope and intercepted
browser behavior, not AWS's effective IAM authorization or deployed OAC signing.
Qualify those only after the complete cost/resource/rollback inventory is approved.
Primary sources and integration details:
[AWS contract research](research/2026-10-22-cap06-lambda-oac-contract.md),
[design](specs/2026-10-22-cap06-cloud-access.md),
plan.
