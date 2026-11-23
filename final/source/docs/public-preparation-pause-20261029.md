# Public acceptance preparation pause — 29 October 2026

The owner requested a usage-limit pause and a checkpoint, intending to return in
about three hours. Stop project execution until the owner resumes. No automatic
restart or reminder was scheduled. This entry supersedes the historical launch
review hold: the owner subsequently said “lets finish this project,” then paused
during local preparation. The previously approved resource/model limits remain
unchanged and unused; a pause alone does not require duplicate approval.

## Safe state at pause

Read-only AWS verification recorded the original host stopped without a public
IP, zero Stockholm EIPs and zero Lambda functions. This public operation has zero
AWS mutations, starts, EIP requests, provider-status GETs and model POSTs. Its
four-hour session clock has not started. No DNS records were changed. The original
encrypted root disk and DynamoDB table remain; retained storage still incurs
usage. The previous RDS trial was already closed and deleted.

Docker Desktop was stopped after the local builds. Process inspection found no
Docker backend/Desktop process, Python test/build process or public-operation
worker. No deadline worker or cloud execution runner was launched. The protected
operation is marked `owner_paused=true`; `local-ready.json` and
`watchdog-ready.json` are absent. Do not manufacture these sentinels to resume.

## Completed local preparation

The native release was rebuilt offline from clean committed source
`44e4952e4374bfa3a94da010d02170b70cf0c0df` with Python 3.12.14 and Node 24.22.1.
The archive SHA256 is
`0144cbd43a156804f221797bd0d733d63d8130f0aae831d1ba7583b5b76d1127`;
the manifest/release SHA256 is
`fd45e5d183b2c585b4974f0ee3650303f779a2e853750415e7f7f68a5ce073a7`.
Native imports, two Storefront restarts, key isolation/refusals and preservation
of uncertain allowance passed. Full qualified Agent startup was **not** exercised
by this build; Caddy verification was adaptation only. No provider/SDK calls.

Both rebuilt startup/controller Lambda ZIPs passed package validation, isolated
Windows smoke and actual AL2023/Python 3.12 Linux smoke with network disabled,
read-only filesystem and synthetic dependencies. The earlier full production
regression remains 1617 passed with two existing dependency warnings; production
source has not changed since that run. Thirteen private operator tests passed
during preparation. These tests do not establish deployed acceptance.

Read-only inventory confirmed Free eligibility, approximately USD179.74 credit,
the retained resources and managed CloudFront policy IDs. Fresh official pricing
queries cover compute, root storage, IPv4, DynamoDB requests and Lambda duration.
The working estimate is USD1.777944961 within the approved USD2, using tighter
working limits of 500 invocations per Lambda plus 240 conservatively additional
ticks. It is an estimate, not a billing hard cap; refresh before execution and
verify remaining service allocations. No free allowances were deducted.

## Resume frontier — operator is incomplete

Private preparation is under `.scratch/cap08-public-preparation/`. Recover
`public-operation.txt`, `native-operation.txt` and `lambda-linux-operation.txt`.
The operation contains pause/read-only receipts and a private source snapshot.
Inspect retained diagnostics and current helpers before running anything; do not
rebuild or restage blindly. `resume-frontier.md` in that private operation records
the remaining specific implementation/review findings.

The operator, resource builder, guest finalizer and cleanup helpers are drafts.
Some review findings were fixed with synthetic tests, but partial-create
reconciliation, independent deadline cleanup, execution orchestration and final
inventory are not yet complete. There is no cloud-ready claim. Finish those
checks locally, including failure paths, before the first AWS mutation. Source
snapshot hashes are recovery evidence, not runtime byte pins.

Keep the exact approved USD2 AWS/Free/USD0-cash, four-hour, two-total-start,
one-EIP limits. The first start is maintenance; the second must be genuine
invitation cold wake. No extra instance, reboot or manual replacement start.
Keep at most four OpenRouter POSTs/USD0.10 within the unchanged non-resetting USD2
key cap, the existing USD0.10 readiness reserve, and at most five key-status GETs.
Read the actual resident ledger baseline once and pin baseline+4; never recreate
the ledger or recompute four fresh slots on restart. Preserve generation 3 and
the existing custody/qualification evidence.

Before launch, refresh credentials, eligibility, prices, authoritative DNS,
operator IPv4 and available session time, then confirm the owner's DNS/Android
availability. DNS creation and restoration are human-only. **No Computer Use or
Brave access.** Keep all preparation offline from deployment until the bounded
runner, rollback and independent cleanup are ready. The actual public HTTPS,
cold wake, desktop/physical Android, live-shopping and genuine idle-shutdown
acceptance checks remain outstanding.
