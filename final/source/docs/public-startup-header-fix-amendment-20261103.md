# Startup CloudFront header-bound fix — 3 November 2026

The approved two-request diagnostic proved that legitimate CloudFront/OAC events
contain 36–39 headers, below 2241 aggregate header bytes, with valid names/values
and the expected HTTP-v2 shape. The original handler rejects more than32 headers.
Both diagnostic updates completed and the exact original startup ZIP hash was
verified restored. The retained EC2 host remains stopped; no cold-start permission
or live model POST has been issued.

## Exact change prepared

Change only `agent/lifecycle/startup.py`: accept at most64 headers instead of32.
Retain the4096-byte aggregate header limit, ASCII/name checks,1024-byte decoded
body limit, strict HTTP-v2 paths/query/cookie checks, exact origin/JSON checks,
durable rate limits, invitation validation and IAM/OAC protection.

The fixed ZIP is derived from the verified44e4952 startup ZIP. Every uncompressed
member except that one source file is byte-identical; the original root handler
is retained. Native application, controller ZIP, provider custody and qualification
binding are unchanged. This is44e4952 plus the explicit transport patch, not the
original artifact hash.

Fixed ZIP SHA256:
`265df9d25f72fa0271eff26594eba6fc9afe307282c1bd3298d76b7cf6522537`

Original ZIP SHA256:
`7d90b216b33f4697354df220764e8a2f79dd35b63bcc1fff2e2c01f72aac5f7d`

## Requested cloud amendment

Upload the one fixed ZIP into the existing private encrypted releases prefix;
permit exactly **one additional update-function-code** against the existing
startup Lambda, pinned to this artifact. Do not reset the two consumed diagnostic
updates. Keep the same function configuration, role, IAM URL, OAC and resources.
Verify Active/Successful and the exact fixed CodeSha256 before edge checks,
invitation issuance or the already-authorized cold wake. Do not replay an
uncertain update: inspect its code hash. If deployment cannot be verified, keep
cold wake blocked and use the existing bounded teardown.

Repeat the existing five edge acceptance checks, then continue the approved
desktop-only acceptance procedure. No new endpoint or authentication bypass.
No additional model allowance, status checks, starts, IPs or resources.

## Unchanged bounds and rollback

Same active session andUSD2 existing-credit ceiling, mandatory Free/USD0cash.
Absolute compute/control end remains01:29:17UTC on3November, earlier supervisor
cleanup cutoff00:09:17UTC; EIP-only deadline03:29:17UTC. Invitation issuance must
still occur before22:34:17UTC on2November. No clock/counter reset or extension.
One additional approximately26MB S3 object stays within the existing1GiB bound.
Existing full teardown removes temporary functions/control artifacts and stops
the original host, followed by owner-only DNS removal, actual TTL expiry and EIP
release. This amendment grants no extra restoration update; teardown is the
rollback if the single deployment is unsuccessful.

## Offline verification

The regression first reproduced400 responses for36/39/64 valid headers. With the
one-line fix, all55 startup tests pass, including invalid invitation denial,
65-header/oversize rejection, origin/body/query/cookie and durable-rate checks.
All78 current private operator tests pass, including separate one-update pinned
authorization and blocking cold wake until the fixed hash is verified. Python
lint and format checks pass. Full regression results are recorded before launch.

Final regression:1622Python tests passed (two dependency deprecation warnings),
199TypeScript tests passed,78private operator tests passed, and all three package
builds passed. Product lint/format and Python lint/format pass. The broad local
repository scans also encounter historical scratch JavaScript (2158lint errors)
and unformatted historical progress/frozen diagnostic documents. These unrelated
local evidence files were preserved; no claim is made that those broad scans pass.

This exact artifact substitution requires owner approval under the project's operating rules'
actual deployment/resource gate; the diagnostic grant authorized only the probe
and original restoration.
