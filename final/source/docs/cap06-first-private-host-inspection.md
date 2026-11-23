# First private Linux host inspection

Executed after explicit owner approval25October2026; see [results](cap06-first-private-host-results.md).
The original pre-approval proposal and its unchanged JSON manifest follow as history.
At preparation time no resource creation had been authorized or executed. This is a
small first cloud stage within the approved Controlled Storefront scope. It does
not authorize application activation, provider spending or key/ledger migration.
The [exact manifest](cap06-first-private-host-inspection.json) binds the reviewed
private account/network/operator/public-key inputs by hashes.

Create one Stockholm t3.small using Amazon AMI ami-0111419d42d14a400, Standard CPU
credits and one20GiB encrypted gp3 root (3000IOPS/125MiBps). Retain the root on
termination. Use one existing public subnet and one primary interface with
automatic public IPv4 explicitly disabled; then associate exactly one EIP.
Import the existing owner-held Ed25519 public key, create one dedicated security
group and allow SSH22 only from the captured ownerIPv4/32. Keep application80/443
closed. Egress is443 only, with no IPv6 rules. Reuse existing network resources
without changing shared subnets, routes, ACLs or DNS. No instance profile or model
credential is installed. Account/AMI/network/key conflicts refuse creation.

The exact new source is023d9f621bc9432b871e519d51e6ce57bb7dc204. Its Linux archive
SHA256 is5e5e3843160225b81b81f3dd79bb960fc82507134ae7a7f58896020d5cd28a23;
manifest SHA256 isefc1f9da4388c24b9e8b312aed2871c1aa7174f78370a531f2400a8c6b9d0757.
Clean build, synthetic captured-client1/5/8 capacity, qualification expiry/default
refusal and independent archive extraction pass; actual-host capacity stays open.

## Finite inspection and recovery

Approval would permit creation only from24October21:00UTC through25October18:00UTC
(25October00:00 through21:00Cairo). No creation follows an expired approval window.
In every case verify stopped/EIP released by the earlier of two hours from actual
launch/allocation and25October20:00UTC (23:00Cairo). Set the guest deadline to the
earlier of90minutes from launch and25October19:30UTC. Retention must receive a new
owner decision by23December18:00UTC; that is less than60days after the earliest
creation in this window. This review date is not permission to delete anything.

The proposed window is at most two cumulative running hours and two EIP allocation
hours. A persistent guest systemd timer calls poweroff at a freshly rendered
90minute absolute UTC deadline and90minutes after boot. Launch explicitly sets
InstanceInitiatedShutdownBehavior=stop. The timer is defense in depth, not a
billing cap: bootstrap/guest failures can prevent it. The operator must stay in
the creation/inspection turn, issue owned StopInstances, observe stopped, release
the EIP and verify no owned running instance/address remains before finishing.
Do not automatically restart or retry a failed launch.

Immediately verify the installed deadline before inspection. Verify SSH host-key
identity using owned EC2 console evidence before connecting; keyscan alone is not
trust. An existing private-key companion file is present, but the SSH agent is
unavailable and private-key possession/passphrase has not been tested. A blocked
SSH login therefore stops the stage and triggers the direct API stop/release
path; it never licenses key replacement or broader SSH ingress.

Inspect the installed Amazon Linux image, package/repository records, versioned
Python/native libraries, systemd252/PID1, UID/filesystem layout, nft/capability/
metadata/log prerequisites and actual host resources. Do not install or run
Shopping Copilot application services in this stage. The verified native release
can be transferred for digest inspection only if within the same narrow egress
and running window; it is not activation or a new model qualification set.

Persist the operation UUID and intended account/network/key/deadline record
before any mutation. Tag each created resource and use the same unique
RunInstances ClientToken. A launch/address API timeout can conceal a successful
creation. Recover exact owned resources using read-only operation-tag/client-token
inventory, then stop/release as appropriate. Do not infer failure, reuse names or
issue another creation attempt to solve an unknown result.

Partial failure removes only this operation's empty unused security group,
imported public-key record and unassociated EIP. Never modify shared networking,
terminate a created instance, delete a volume/snapshot or discard retained data
without a separate decision. Keep the stopped instance/root for at most60days;
retention must be revisited before that deadline. No deletion automation is added.
Actual host observations may change the later provisioning proposal; they do not
close untested production acceptance gates.

## Credit estimate and approval boundary

The [dated primary-source worksheet](research/2026-10-24-cap06-first-private-host-cost.md)
prices the scope at USD3.39846642 gross before tax/credits, including the entire
60day root retention, 0.01GiB charged egress and100incidental KMS requests. A
conservative storage-month sensitivity is USD3.63732357. The proposed allocation
is USD4.50 of existing AWS credits, with zero cash, no top-up and no plan upgrade.
This is an estimated allocation under stated quantities, not a guaranteed bill.
No free allowances were assumed. Current account Free-plan eligibility remains
mandatory; reject any operation asking for Paid/advanced features.

Approval of this concrete stage would cover only these named quantities/settings,
existing-key SSH inspection, direct stop/EIP release and harmless cleanup of its
unused dependencies. No general production deployment, active model allowance,
public DNS/TLS or other resource is included. The full graduation dossier remains
inactive. The separately recorded native synthetic capacity check also cannot
establish EC2, remote-model or browser capacity.
