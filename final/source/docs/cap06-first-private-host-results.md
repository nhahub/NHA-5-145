# First private AWS host inspection completed

25October2026. The owner explicitly approved the exact
[first inspection proposal](cap06-first-private-host-inspection.md) and its
USD4.50AWS-credit allocation. The approved SSH-only stage is complete. AWS confirms
the instance is stopped, its EIP has been released and the encrypted root is
retained. No application or model serving was activated.

## Executed scope and verification

Created one Stockholm t3.small, one20GiB encrypted retained gp3 root, one dedicated
security group and an import of the existing owner public key. One primary
interface had automatic public IPv4 disabled. Only then was one temporary EIP
allocated and associated for inspection. Standard CPU credits, disabled detailed
monitoring, baseline3000IOPS/125MiBps, no instance profile, required IMDSv2/hop1
with IPv6metadata disabled and explicit shutdown=stop were verified in AWS.
The security group allows SSH22only from the captured ownerIPv4/32, egress443only
and no application80/443 ingress. Default all-egress was removed before launch.
Shared networking, DNS, IAM runtime roles and provider custody were unchanged.

The existing private key's public derivation matched the approved public key;
private bytes were neither copied nor printed and no replacement key was generated.
SSH host identity was verified against the owned EC2 console fingerprint before
connection. Dedicated known_hosts and disabled inherited SSH configuration kept
global trust untouched. Cloud-init installed the approved stop timer, whose
exact user-data bytes were verified through AWS. Its active/enabled/persistent
state and future deadline were verified before the rest of the guest inspection.

The finite read-only SSH payload completed32bounded sections, with9508stdout
bytes, empty stderr and exit0. No packages, application users, project directories,
service units or model credentials were installed. A4423680byte native release
archive was transferred owner-only(mode0600) and independently hashed on the host:
5e5e3843160225b81b81f3dd79bb960fc82507134ae7a7f58896020d5cd28a23.
It was not extracted or executed.

## Actual base image observations

| Item                                 | Observed                                                   |
| ------------------------------------ | ---------------------------------------------------------- |
| Amazon Linux                         | 2023.12.20261021                                           |
| Kernel                               | 6.18.54-121.166.amzn2023.x86_64                            |
| PID1/systemd                         | systemd252.23-15.amzn2023                                  |
| OpenSSL                              | 3.5.8                                                      |
| System Python                        | 3.9.25                                                     |
| Application Python3.12/Node/nftables | not installed                                              |
| CPU/RAM                              | 2vCPUs;2002350080bytes RAM; no swap                        |
| Root filesystem                      | 20GiB device, XFS;19636555776bytes available at inspection |
| Cloud-init                           | 22.2.2; completed                                          |
| Project accounts/directories         | absent                                                     |
| Journal size                         | approximately16MiB                                         |

The inspection user's effective capabilities were empty, but NoNewPrivs and
Seccomp were not enabled for that ordinary SSH session. These are base-image
facts, not evidence that application service sandboxing, UID/metadata separation,
Caddy capabilities or log/reboot behavior are qualified. nftables installation,
versioned application Python, Node, pinned runtime environment and service layout
remain concrete provisioning work. Do not replace system Python3.9.

## Stop, cost and retained custody

Launch was requested24October21:14:06UTC(25October00:14:06Cairo). Stopped state was
observed at21:17:38UTC; EIP release and absence were confirmed by21:18:01UTC.
Launch-request-to-stopped and EIP-allocation-request-to-release observation bounds
were212.616and208.622seconds, comfortably below the approved two-hour limits.
These are conservative observation intervals, not finalized AWS billed duration.
A later read reconfirmed stopped state, no public IP, no owned allocated EIP,
Standard credit mode, retained encrypted root and the active Free plan.

The stopped instance, attached root, security group, primary interface and imported
public-key record remain recorded privately under the exact operation UUID. The
root keeps accruing storage cost. The approved retention decision is due
23December2026at18:00UTC; no volume deletion, instance termination or deletion
schedule is authorized. USD4.50was an estimated credit allocation for the exact
stage/retention scope, not a claim that this amount was spent or a hard bill cap.
No cash or Paid-plan upgrade occurred. Billing is not yet finalized.

Two local CLI diagnostics were retained: an unsupported Windows file URI failed
before an API call, and console Unicode output failed locally after a read. They
were corrected without retrying resource creation. The single launch and address
allocation were not repeated. Eleven authorized resource writes include stop,
disassociation and EIP release. Every outcome is reconciled by operation ownership,
including retained volume/interface inventory; nothing was inferred absent from
an API timeout. The stop permission's deliberate dry-run refusal confirmed access.

## Restart handoff

The inspection timer remains enabled and persistent, with absolute deadline
24October2026at22:44:06UTC(25October01:44:06Cairo) and OnBootSec90minutes.
Do not automatically restart this host. A later boot after the missed calendar
deadline may trigger immediate poweroff; OnBootSec does not postpone that calendar
catch-up. Actual future-boot behavior was not tested. A separately approved next
stage must rebind the deadline first if starting with sufficient margin before
that original deadline; after it, review a recovery method before starting.
Do not repeatedly boot to race the timer or assume changed user data runs early
enough to repair it. No additional start, timer change or recovery infrastructure
was performed in this completed inspection.

The next local work is a concrete offline provisioning procedure using the already
verified vendor runtime/wheel/tool records and these actual host facts. Privileged
installation, any restart/recovery, real key/allowance migration, remote authority,
application capacity and public activation keep their separate gates. Do not create
another host by treating this inspected instance as missing.

The [sanitized execution receipt](../eval/evidence/cap06-first-private-host-inspection-20261025.json)
binds the human approval, immutable original proposal, private API/SSH/custody
records, safe final observations and actual limits. Full resource IDs, account/IP,
SSH fingerprints and raw console details remain in the ignored owner-held record.
