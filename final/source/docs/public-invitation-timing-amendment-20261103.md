# Invitation timing amendment — 3 November 2026

The owner approved the exact startup header fix after the original invitation
issuance cutoff had passed. The premature helper precondition refused before
any cloud write; its invitation-only cutoff was then separated from the approved
code-update window. The single authorized code update is now complete, the exact
fixed hash verified, and all five edge acceptance checks pass. Host still stopped;
one maintenance Start/one EIP consumed, no cold-start permission or live model POST.

## Requested change within the same session

Allow issuing the one desktop invitation until **00:54:17 Cairo on3November**
(22:54:17UTC2November; original first-write plus85minutes), replacing the original
plus65-minute issuance cutoff. Set invitation expiry to **01:09:17 Cairo**
(23:09:17UTC; plus100minutes), replacing plus90minutes. This is one fixed absolute
window, not a reset or a new session. No replay of a consumed invitation/start.

Require the desktop driver to start before **00:59:17 Cairo** (plus90minutes),
and close before **01:04:17 Cairo** (plus95minutes). If that bound cannot be met,
stop this attempt and use existing teardown; never shorten/fabricate the60-minute
idle proof. Close/revoke the desktop invitation after the driver. With closure
by plus95minutes, genuine idle can finish by plus156minutes, before the unchanged
plus160-minute supervisor cleanup cutoff at **02:09:17 Cairo**.

The owner confirms app.scpilot.tech and store.scpilot.tech tabs are closed and
will keep them closed until the genuine-idle result is reported. The automated
test opens/closes its own isolated browser; the registrar DNS page may stay open.
This confirmation plus the actual driver closure will support the browser-closure
receipt; no claim is made that a user confirmation occurred before approval.

## Everything else unchanged

ExistingUSD2 AWS-credit ceiling, mandatory Free/USD0cash, same host/table/profile,
at most2totalStarts/1EIP, remaining one nonrenewable120-second cold-start grant,
maximum4OpenRouter POSTs/USD0.10 and5statusGETs inside the existing nonresetUSD2 key
cap/readiness reserve. No new code update, resource, model allowance or phone test.
Absolute four-hour compute/control end03:29:17Cairo and six-hour EIP-only end
05:29:17Cairo remain. Owner-only DNS removal, authoritative absence, actual7200s
TTL wait, EIP release and full temporary-control teardown remain mandatory.

The private operator requires a separate owner approval receipt pinned to this
document; its default65/90-minute window is unchanged without that receipt.
New offline checks exercise both default and explicitly approved late bounds.
This amendment needs approval because the earlier approved proposal fixed the
original issuance/expiry timing; the project's operating rules requires exact acceptance/deployment
bounds. It requests no extra financial allocation and authorizes no new session.
