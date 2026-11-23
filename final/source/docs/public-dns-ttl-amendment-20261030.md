# Public acceptance DNS TTL amendment — 30 October 2026

Prepared for owner review during the existing session; not executed.

The registrar offers an explicit two-hour TTL and longer values. Its Auto value
has not been verified as 300 seconds. Use the explicit two-hour value for only the
two approved app/store A records, then independently verify their authoritative
TTL is at most 7200 seconds. Do not change nameservers or other records.

Keep every existing approval bound, with one narrow exception: allow the same
single temporary EIP to remain allocated for the measured DNS cache-expiry wait,
until at most six hours from the original first write. The original session began
07:16:43 UTC; compute/application activity still ends by 11:16:43 UTC, and the EIP
must be released by 13:16:43 UTC. The existing earlier operator cleanup cutoff
remains unchanged. No additional host start, instance, disk, table, provider
request, model allowance or public operating window is authorized.

After genuine idle shutdown (or earlier abort), close public ingress, disable
startup/control delivery, stop the original host, obtain owner removal of both A
records, verify absence at every authoritative server, and wait the larger of
7200 seconds and the actually measured TTL before releasing the EIP. Do not
remove DNS during the healthy idle test: the controller requires signed HTTPS
health observations throughout that test.

Only the EIP may remain during this additional wait, apart from the already
approved disabled CloudFront deletion tail. It must not serve an application.
Use the existing finite local cleanup supervisor and independent final inventory;
keep the canonical disabled allowance and retained storage. No ongoing demo.

At the freshly verified IPv4 rate USD0.005/hour, two additional EIP hours cost at
most USD0.01 before contingency. The conservative estimate becomes approximately
USD1.791 including contingency, inside the unchanged USD2 existing-credit ceiling.
Free plan and USD0 cash remain mandatory. This amendment does not reset the
original clock, credit allocation, start counters or model/provider limits.
