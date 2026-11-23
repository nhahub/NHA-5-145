# Controlled Storefront public desktop acceptance — 3 November 2026

Status: **desktop acceptance and independent cleanup verification passed**.
The original IP-retention timing exception is recorded below.

## Scope and verified behaviour

The graduation scope remains the Controlled Storefront on the prepared Linux
host in Stockholm, using the qualified OpenRouter fallback. Physical Android
testing is excluded by the owner. Independent storefront generalisation remains
outside this target.

The fresh recovery operation is `5c467f97-9f29-4a79-a6fa-d95cdcb2c422`, with
lifecycle generation 5. Its actual public Chromium test used trusted HTTPS,
submitted one Egyptian-Arabic request to clear the cart, and made 147 application
requests. The evidence verifies:

- Independent shopping-cart identities.
- Sensitive Field values excluded from the Snapshot.
- An unchanged cart before bound Confirmation and an empty cart afterward.
- Refresh recovery without replaying the shopping request.
- Reopening the event stream and keeping invitation codes out of URLs/storage.
- Invitation-authorized cold wake and signed application readiness.

After browser closure and invitation revocation, the controller stopped the
host automatically. Independent AWS/lifecycle observations verified generation 5
stopped after **3,755.376 seconds** of inactivity, with no leases or pending
command. CloudTrail independently verifies two successful starts and the natural
controller stop at **03:22:46 Cairo**. The physical stopped observation was at
**03:24:03 Cairo**. CloudFront also reached global `Deployed` status.

## Provider accounting and source

The authenticated final shutdown receipt verifies one new settled OpenRouter
attempt, no new uncertain attempts, and **$0.0011298** live spending. The ledger
is disabled, **$0.0988702** of unused live allocation was withdrawn, the **$0.10**
readiness reserve remains, and previous charges/holds are preserved. The original
non-resetting **$2** provider key cap is unchanged.

The native release remains pinned to source `44e4952`. The startup transport
fix, saved in local commit `9c1902a`, accepts up to 64 headers while preserving
the 4,096-byte aggregate limit,
invitation checks, IAM/OAC protection and other transport validation. Its ZIP
SHA256 is
`265df9d25f72fa0271eff26594eba6fc9afe307282c1bd3298d76b7cf6522537`.

Recorded verification includes 1,622 Python tests, 199 TypeScript tests and
successful builds; 117 private operator checks; and a fresh focused startup
regression of 55 passing tests. The public case above is actual deployed
behaviour, separately recorded from synthetic checks.

## Cleanup and timing exception

The registrar's two temporary `app`/`store` A records were deleted under the
owner's explicit delegated cleanup authority. Their UI absence was verified at
03:26 Cairo. Full authoritative A/AAAA/CNAME absence was first verified at
**09:36:02 Cairo**; the unchanged 7,200-second cache gate therefore permits IP
release only after **11:36:02 Cairo**.

The original EIP-only cutoff of **07:38:50 Cairo** was exceeded. Local helper
heartbeats stopped advancing, no helper processes remained on morning resume,
Windows reported a restart at **09:29:48 Cairo**, and AWS sign-in had expired.
The host remained stopped. The owner completed sign-in and renewed the instruction
to finish autonomously. Cleanup resumed with no new starts, allocations, provider
requests or additional budget, preserving the original timestamps and recording
the timing exception explicitly.

The inherited IP was released by **11:36:31 Cairo**, after **7,229.285 seconds**
from verified authoritative absence. Independent resource inventory passed at
**11:37:44 Cairo**. Final desktop acceptance closed at **11:38:04 Cairo**; a further
independent root check confirmed the host stopped, no public IP or owned EIP,
temporary resources absent, and the AWS Free plan active.

Public ingress is closed. Generation 5 is stopped and recoverable with no leases
or pending command. The cleanup supervisor, closure observer and temporary local
execution request have finished. No local demo listeners remain on ports 4000,
4100 or 8000. The original stopped host, encrypted root disk and existing table
are retained under the approved retention scope; retained storage still uses
credits. Further public activation requires a new bounded operating session.

Detailed evidence and the latest operational status are indexed in
`PROJECT_CHECKPOINT.md`; protected receipts remain in the recovery operation
directory under `.scratch/cap08-public-preparation/`.
