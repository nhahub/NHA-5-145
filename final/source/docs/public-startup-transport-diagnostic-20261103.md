# Bounded startup transport diagnostic - 3 November 2026

The desktop-only session is active, but the original EC2 host is stopped after
successful maintenance staging and public HTTPS. No cold-start permission has
been issued and no live model POST has occurred. Public waiting delivery and
anonymous Function-URL/private-S3 denial checks pass. CloudFront control requests
reach the original Lambda handler but return its transport-level400denied before
any invitation/lifecycle processing. Existing code deliberately omits raw events
and transport exception details, so the failing field cannot be established yet.

## Concrete diagnostic prepared for approval

Temporarily replace only the existing startup Lambda ZIP's root handler.py with
the locally tested metadata-only public_transport_probe.py. Keep every other ZIP
member byte-identical. Its HTTP response contains only fixed validation reason,
type/shape booleans and header/body lengths/counts. It returns no header names or
values, cookies, body, path, query, caller identity, configuration or credentials.
It makes no SDK, DynamoDB, provider or EC2 request and does not log the event.

Upload this one ZIP into the already-owned private encrypted S3 releases prefix.
Permit exactly two update-function-code calls against the current startup
function: diagnostic ZIP, then the original hash-verified startup ZIP. Retain the
same256MiB/30s/reserved1 configuration, execution role, IAM-authenticated URL and
always-sign OAC. No new function, role, resource, public route or IAM permission.
No direct anonymous access or diagnostic bypass of the existing edge/IAM gate.

Make at most two HTTPS requests through the existing CloudFront control routes:
GET/status and POST/wake with an invalid unissued code. Retain only safe metadata.
Restore the exact original code hash and verify Active/Successful before any
invitation or cold-start permission. Block wake while restoration is unverified.
If an update is uncertain, reconcile its actual code hash rather than replaying
the update. If restoration cannot be proved inside the original bounds, tear down
the temporary function/control resources and keep the EC2 host stopped.

## Bounds unchanged

This uses the same running desktop-only session and its existingUSD2 credit
ceiling, mandatory Free plan/USD0cash and absolute compute end01:29:17UTC on
3November, with the earlier160-minute cleanup cutoff. EIP-only deadline remains
03:29:17UTC. No clock/counter reset, new host start, model POST or key-status GET.
The one additional approximately26MB S3 object and two HTTP requests stay within
the existing1GiB S3/admin-transfer and2000edge-request bounds. No extra financial
allocation is requested. Original runtime/native release and provider custody
remain untouched.

Only this two-update, two-request diagnostic is requested. A production transport
fix would be prepared and tested from the observed metadata and reviewed before
replacing the original artifact for acceptance. Diagnostic results are not an
application or readiness pass. The temporary startup code replacement needs this
explicit amendment because the existing grant pins the original verified ZIP.
