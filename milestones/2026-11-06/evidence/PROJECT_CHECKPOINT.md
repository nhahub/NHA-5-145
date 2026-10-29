# Project checkpoint

**Last updated:** 2026-10-28

## DEPI System Analysis and Design refresh - 2026-10-28

Owner reprioritized preparation of the 6 November report against the substantially
implemented application. docs/system-analysis-design.md and system-design-views.md
now cover per-Shopper commerce, the physical SQLite catalogue/allowance ledger,
current intent/advice interfaces, task/Confirmation/recovery, actual selected
classes and the Stockholm network/native UID/metadata/log design. Twelve editable
draw.io sources and matching previews accompany the vector PDF; all 21 original
requirement IDs retain their meanings and distinguish local evidence from open
acceptance. Historical local regressions are cited, not rerun or enlarged.

Requested find-skills discovery selected the read C4 Architecture and Technical
Writer guidance; no global installation. docs/system-design-skills.md records
sources, observations and the restricted XML rendering fallback (no Desktop CLI).
The separate scripts/export_system_design.py validates source text, links, bounds,
requirement IDs and geometry; rebuild and package paths are documented in
docs/system-design-submission.md. The review record binds inspected pages/figures
to the exact PDF digest. Preparation does not upload this November report.

The product frontier remains native host/runtime lock and the existing actual
host/model/account/cost/resource/rollback acceptance gates. This revision makes
no runtime change, AWS call, inference call, deployment or spending change. Prior
October reports are historical; no independent-storefront prerequisite is added.

## PR3 clean-CI readiness fixes — 2026-10-24

The first Ubuntu CI runs exposed clean-environment assumptions before merge:
a RawClient admission test lacked an explicit service secret; one browser test
assumed the first tab won concurrent initialization; legacy pnpm deploy forced
unfrozen re-resolution and required uncached macOS-only fsevents metadata even
for a production offline build. No application safety check was relaxed.

The admission test now supplies a synthetic explicit environment. The two-tab
test accepts either legitimate owner while asserting exactly one enabled tab,
shared session/cart, disabled observer and explicit takeover; forced reverse
initialization is also covered. Packaging keeps the isolated manifest workspace,
uses its temporary injectWorkspacePackages override to select pnpm's frozen
production deployment path, and retains --offline. Source lock/config untouched.
CI installs pinned eval/requirements-cloud.txt so authority/host tests run.

RED cases reproduced; focused GREEN:80DynamoDB,8admission,8shopper-isolation,
11release/recovery. Fresh review of the four-file fix:0findings. Clean AL2023/
pnpm11.19.0 diagnostic reproduced the metadata failure and frozen-path success;
its Git provenance was stubbed for the diagnostic, not a production build claim.
Actual CI/merge receipts are on https://github.com/Homd11/shopping-copilot/pull/3.
The next product frontier remains native host provisioning/runtime lock and
existing host/model/account/cost/apply acceptance. No AWS activation, inference,
production keys, DNS/TLS or spending authority changed through CI integration.

## CAP-06 local host isolation and lifecycle diagnostics — 2026-10-23

Separate copilot/copilot-store/copilot-proxy UIDs and minimal native Store/proxy
settings are implemented. Agent config now .../agent/host.json; Store .../store/
store.json; proxy .../proxy/proxy.json. Private-reader rules remain unchanged;
readiness/ledger Agent-only, distinct owner-only Agent/Store service-key copies,
proxy no application keys. Agent group/read-only catalogue boundary and Store
setgid2750/db0640/umask0027 are prepared; no actual account/migration/provisioning.

Root stdlib metadata helper validates exact config/release/fingerprint/bound UID
before one fixed bounded nft call. New required root/NET_ADMIN oneshot owns only
its inet output chain; each application Requires/BindsTo/After it. Failed barrier
prevents startup; stop leaves rules and stops applications. Root remains trusted;
external root rule deletion is not detected by active oneshot state. Inventory
now counts4local services (3applications+1barrier), with AWS counts/costs unchanged.

Fixed per-service lifecycle hooks/log directories use descriptor nofollow checks,
private regular single-link files, one-second advisory lock, file/directory fsync,
64KiB/file+2backups/seven-day prune on write. Only time/service/event/fixed outcome;
no raw child/error/environment/key output. Failed prestart logging refuses launch.
Lifecycle is not readiness; filesystem failures cannot guarantee a failure record.

Fresh derived production artifact passed nonroot AL2023/Python3.12.15/glibc2.34
full default settings/13refusals/29diagnostic wheels/six native imports/Node24.13.0
exec/auth/restart/persistence/Agent early refusal/Caddy2.11.7 adapt+captured handoff.
Separate disposable root-bootstrap proof switches real synthetic UIDs: key/state/
proc-environment/signal denials, no child effective caps, live group-readable WAL,
Agent denied writes, two native Store restarts, seven unsafe log cases/three I/O
failures/rotation/retention/fsync/lock/eight writers. Store-closed/missing-WAL
Agent refusal is expected; Store startup prepares sidecars, no immutable/write bypass.

Real nft1.0.4 fake IPv4+IPv6 metadata packets allow only root/Agent; Store/proxy/
unrelated UID denied, ordinary loopback preserved, repeat semantics/failed-batch
atomicity/unrelated table preserved. Network none/read-only root, fixed caps and
bounded tmpfs; only loopback, no actual IMDS/account.14official hash-checked RPMs
extracted as test tools, not installed/signature/security approved. Six units pass
static systemd255.4 with inert stubs, not actual systemd252 boot/reboot acceptance.

Final full Agent+eval:1318pass/no skips/2upstream deprecation warnings in935.10s.
Initial run1310pass/8fixture setup errors after lint removed an imported fixture;
restored import,8focused and30new-module pass, then clean full rerun. Repository
cacheprovider is disabled, so --lf reran all1318 rather than selecting failures.
TypeScript199pass, workspace/production build, Ruff262, pip and scoped ESLint pass.
Fresh whole-slice review:0Critical/0Important/1Minor, handoff wording corrected;
no deferred finding or second review. Evidence/guide:
eval/evidence/cap06-host-isolation-20261023.json, docs/cap06-host-isolation.md.

Next: approved native Linux provisioning/production lock and actual host UID/
capability/systemd252 boot/dependency/reboot/log-retrieval/metadata acceptance;
full Agent lifespan/signed readiness/capacity, current account/credits/workload,
Bedrock usable quota/strict qualification and final bound resource/cost/rollback
approval remain open. No AWS/account/model call, real key/state/user change,
install/activation, DNS/public TLS, extra spend, upgrade or push. All model/
authority/uncertain-outcome/Free/Stockholm/USD0cash gates persist; CAP04/05/06/07
and cloud acceptance are not closed by local implementation.

## CAP-06 inactive concrete apply dossier prepared — 2026-10-23

docs/cap06-apply-proposal.md and cap06-apply-inventory.json consolidate exact
proposed names/settings/counts, phased bindings, credential/state custody,
activation, code rollback and targeted teardown. Inert data/docs only, not a stack,
CLI input or an approval-ready result. Generated IDs remain null; distinguish
pre-creation account/network/artifact facts, later creation receipts and
activation/authority/key references. No synthetic ID is a real account binding.

Base proposal explicitly counts3runtime roles/3inline policies/1profile,2Lambdas/
2log groups/2OACs/1custom control forwarding policy and one each host/root volume/
retainedEIP/table/private bucket/distribution/dedicated host security group/owner
public-key import, plus2registrarAchanges and3host services/target. Shared existing
network not created/deleted. Extra SG/SSH administration/names/settings/native
Linux provisioning are builder proposals, not new owner adoption. Conditional
group/schedule/invoke-role/metric/2alarms remain unadopted, inactive, separately
costed; no third function/new notification or administrative service.

Proposed build uses clean reviewed native Linux output and the28tested runtime
wheels (no diagnostic packaging); exact interpreter/lock/security approval and
native build/provisioning remain open. Owner-scoped SSH copies verified artifacts;
host role has no S3 artifact/backup or EC2-control grant. Host policy bound review
still needed; model InvokeModel grant held until qualification/spend authority.
Secret values absent, actual allowance/identity/key generation never performed.

Pure existing renderer checks with in-memory synthetic bindings pass: both
function/log/OAC/header contracts, disabled finite60day observation documents,
closed alarm/adoption/apply/provider flags, null real bindings, candidate admission
limits and phase-field coverage. Decimal rows/sensitivities independently agree.
Fresh review found2Important and2Minor instruction gaps; primary addressed all
as material to a usable apply/rollback record in one docs/data-only pass: private
config must be owner-only and readable by consuming UID (no root0600 shortcut),
first deployment uses closed safe-stop/no invented previous-release hash,
observation approval is conditional for base-only private preparation, and host
profile/inline policy/role cleanup is explicit. Owner-driven observations after
schedule disable are explicit. Post-fix consistency/format/whitespace pass; no
second independent review or runtime suite rerun for unchanged code. Evidence:
eval/evidence/cap06-apply-dossier-20261023.json. No deferred findings.

Important newly explicit gap: all prepared host units share copilot UID; IMDSv2/
hop1 alone and a copilot UID-owner exception cannot isolate Storefront/proxy from
Agent role credentials. Process/service credential isolation needs a reviewed
implementation and reboot/failure evidence. Current units also discard streams;
durable redacted host diagnostics and actual service/capability/capacity remain
unqualified. Do not fix either gap by an unreviewed provisioning workaround.

Costs carry23October Decimal scenarios, no new prices or fit claim:46.253592base+
22.1066776conditional=68.3602696infra;79.3902696combined;120h50.8782696;
30snon-tick sensitivity102.7236496. USD80unvalidated,11futuremodel allocation
unapproved, existing0.03held/0.04diagnostic authorization unchanged. Historical
handoff now points to the corrected reconciliation. No current-account proof.

Next: host process/credential isolation and durable redacted diagnostics, with
native production provisioning/lock; then remaining account/workload/model and
bound resource/cost/rollback acceptance before any apply. No AWS account/model/
credential/resource/production-key/DNS/TLS API/write, install/activation, extra
spend, upgrade or push. Public primary AWS documentation only was checked.
All previous model, safety, Free/Stockholm/USD0cash and uncertain-outcome fences
persist; no cloud/model gate is closed by this dossier.

## CAP-06 full offline Linux host rehearsal and cost reconciliation — 2026-10-23

Full original HostSettings/default POSIX reader and protected native Storefront
launcher passed in retained official Lambda AL2023.12/Python3.12.15/glibc2.34
linux-amd64 image, digest `25aee9bac65f131c5d090d3e3a36ccf232d65cf3e6c1dbd0bffd43ca7ce34406`.
Network none/read-only root/non-root10001/no capabilities/no-new-privileges;
1CPU/1GiB/no additional swap/64pids, bounded tmpfs and240second outer timeout.
Only verified test inputs/binaries mounted read-only; no credentials/home/socket.
29 pinned diagnostic wheels including Linux uvloop0.22.1 and packaging26.3;
actual Linux extras dependency closure and six native extensions verified.
Production Python locks and runtime unchanged. Native Node24.13.0/Caddy2.11.7
acquired from public vendor archives with digest evidence, no system install.

New eval/linux_host_fixture.py derives a bounded portable test archive from the
verified production build at b2f0290 (manifest truthfully source_dirty=true for
untracked preparation). Initial flattened links broke native Node dependency
resolution; link-topology regression watched RED/GREEN. Preserve193 verified
internal pnpm links as relative Linux links,742 regular files/3361794bytes;
not byte-identical Windows artifact or an adopted installation artifact. Original
manifest and derived digests remain in eval/evidence/cap06-linux-host-20261023.json.

Thirteen full configuration refusals passed. Native Storefront exec/restart twice
preserved catalogue history and disabled synthetic allowance/uncertain reservation;
test endpoint404 and private catalogue auth enforced. Actual Agent module import
and active-loop refusal only, no SDK/app construction/readiness. Caddy version/
adaptation passed; proxy run handoff captured before exec, never public run or
validate/ACME. Real EC2/PID1 systemd252, service UID/protected provisioning,
production Linux lock, capabilities/signals/capacity, TLS/DNS, IAM/OAC/events,
account access and model/cloud acceptance remain open. This advances the offline
Linux seams only. Guide:docs/cap06-linux-host-rehearsal.md.

Focused fixture/host/config/bootstrap/check/release/browser regression138passed,
no skips221.04s; two upstream websockets deprecation warnings. Ruff check/format
254files and pip check pass. Full release compiled with existing builder and
the final offline native rehearsal passed; no blanket unrelated model rerun.
Changed Markdown/JSON formatting and whitespace pass. Default ESLint encountered
compiled JS in the ignored new rehearsal tree; excluding only that generated tree
passes all source lint. Exact command/initial failure recorded in evidence.
Fresh read-only review clear, independently verified every retained digest,
packaged Python parity and Decimal row. Independent Windows run87passed plus
11setup errors from one Node catalogue-seed exit3221226505; isolated11bootstrap
rerun passed7.33s without changes/reset. Unexplained transient retained in evidence,
not erased or identified as a change regression. No deferred review findings.

Current public-rate inventory review and primary Decimal recomputation replace
the old55.50+23 arithmetic as evidence of budget fit: explicit continuous60day
example68.360270 infrastructure /79.390270 including the unapproved11future-model
planning allocation and separate existing0.03diagnostic hold. 120EC2hours gives
50.878270 combined; non-tick Lambda30s instead of2s gives102.723650 combined.
Two functions/edge traffic and shared table/log allowances now explicit. These
are unmeasured scenarios, not caps, account balance/credit eligibility or proof
USD80 fits. Scheduler/group/role/metric/two alarms remain conditional unadopted;
selected inventory and diagnostic/model authorizations unchanged. Sources/assumptions:
docs/research/2026-10-23-cap06-inventory-reconciliation.md.

Next: finish the exact inactive apply inventory/resource bindings and rollback/
cost proposal, including production Linux dependency/provisioning choice and
remaining workload/account evidence. Exact apply approval, Bedrock quota and
qualification and all existing acceptance gates remain required. No AWS/account/
credential/model/resource/production-key/DNS/TLS call/write, unit installation/activation,
upgrade, extra spend or push. Stockholm/Free/USD0cash and all safety fences persist.

## CAP-06 inactive Storefront/Caddy host bundle prepared — 2026-10-23

Prepared explicit `deploy.host_component` store/proxy selection using the existing
protected HostSettings and exact executing release. Storefront uses fixed Node24,
minimum24.13.0 and only production origins/secret/catalogue/lexical configuration;
proxy uses fixed Caddy2.11.7 and the verified public profile/Panel root plus
retained `/var/lib/shopping-copilot/caddy`. Both use clean child environments,
bounded fixed version checks and execve, without a shell, SDK construction,
provider call, parent environment mutation or arbitrary command/profile override.
Catalogue is checked read-only; proxy storage must already have protected
nonsymlink ancestors and current-UID owner-only rwx permissions. No state/key,
catalogue, certificate or allowance is initialized, reset or restored by launch.

New packaged `shopping-copilot-host.target` Wants Storefront/Agent/proxy; members
are PartOf the target with independent bounded failure restarts, store-before-
Agent-before-proxy order and explicit conflict/order against the legacy unit.
Legacy runtime unchanged. Only the target is intended for later enablement.
Type=exec and active target describe process launch, not HTTP/TLS/model readiness;
signed readiness and the closed provider gate persist. No uncertain Action replay.
Agent keeps its1GiB ceiling, new native services256MiB/64tasks each; these are
ceilings, not measured capacity or an allocation. Only Caddy has ambient/bounding
CAP_NET_BIND_SERVICE and storage-only write access. Actual capability inheritance,
native binaries, protected provisioning, systemd252/AL2023 operation, signals,
observability/capacity, public TLS/DNS and all cloud/model acceptance remain open.

Primary-source research and fresh builder check completed. RED missing module/
units then27passed5.91s; component/real packaged production Storefront twice and
real-Caddy adaptation31passed22.95s/no skips. Storefront test routes remained404,
private reads required the fixture secret, catalogue history unchanged; Windows
harness selects installed Node/adds SYSTEMROOT, not POSIX exec acceptance.
Ubuntu systemd255 static verification accepted five units with inert disposable
root stubs; no service started. Eleven actual Linux private-file/storage primitive
checks passed, including symlink/FIFO/hardlink/permissions/ancestor refusal. Exact
AST-extracted functions only, not full HostSettings/real-host acceptance.

Fresh review independently78passed/1deselected24.35s. Its quoted-path robustness
finding was treated as important to the fixed-profile handoff: normalize Panel
path separators and refuse quotes/remaining backslashes/control/DEL before exec,
ordinary spaces supported. Seven character cases plus command integration watched
RED then GREEN;35component unit cases passed6.95s. No deferred minors. Initial
full suite1099passed340.33s; final post-fix results are recorded in
`eval/evidence/cap06-host-services-20261023.json` alongside source hashes, Linux
limits, review and checks. Guide:`docs/cap06-host-services.md`.
Final post-fix all-Agent/host/control/package/proxy/fresh-release/browser suite:
1107passed/no skips345.65s, two upstream websockets deprecation warnings. Ruff
check/format251files, pip, TS lint, changed Markdown/JSON Prettier and whitespace
pass. Quoted-path fix is verified by primary RED/GREEN and final broad tests;
reviewer independently ran78focused cases before that fix, not the final suite.

Next: full protected Linux host configuration/executable acceptance and reconcile
the conditional observation inventory/cost/credit proposal. Separate exact
resource/cost/rollback apply approval, effective IAM/OAC/event/account eligibility,
Bedrock quota/qualification, deployment and cloud acceptance remain required.
No AWS/model/credential/resource/key/DNS/TLS call/write, public ACME run/validate,
unit installation/activation, upgrade, extra spend or push. Free-plan/Stockholm/
zero-cash and all open gates persist.

## CAP-06 Linux artifacts and explicit host launcher prepared — 2026-10-23

Both unchanged22October role ZIPs passed external-digest verification, isolated
Python3.12 imports and injected fixed-role delegation on Ubuntu24.04.3/Python3.12.3
and official AWS Lambda Amazon Linux2023/linux-amd64/Python3.12.15. Image pinned:
`public.ecr.aws/lambda/python@sha256:25aee9bac65f131c5d090d3e3a36ccf232d65cf3e6c1dbd0bffd43ca7ce34406`.
No network or SDK construction; no host credential/checkout mount; read-only root,
capabilities removed, no-new-privileges, one CPU/256MiB/64processes/128MiB tmpfs.
Probe verifies dependency provenance/versions/models/CA and generic fixed-role
failure/delegation. This closes the exact-artifact AL2023 import execution check,
not RIE invocation, actual Lambda, IAM/OAC/event/account or integration acceptance.
Exact ZIP hashes remain those in the22October observation section; no rebuild.

Docker's stale inaccessible runtime dockerInference endpoint initially blocked
startup. With Desktop stopped, runtime directory only was preserved as
`C:/Users/pc/AppData/Local/Docker/run.stale-20261023-01`; regenerated runtime and
Linux API recovered without reset/data purge. Owner subsequently updated Docker;
fresh checks report Desktop4.96.3/Engine29.9.2/API1.56 and successful Linux runs.

Prepared `python -B -m deploy.host_agent --config ABSOLUTE_PATH`: default protected
POSIX settings and exact-release app construction happen before the event loop.
Uvicorn receives the prebuilt app, one process/127.0.0.1:8000/lifespan on, no
reload/proxy headers/access log/server header or provider qualification switch.
Factory exposes owned async cleanup, awaited on the same server loop in finally
even if configuration/server construction or binding fails before lifespan.
Normal/cancelled lifespan plus final cleanup closes SDK once after draining work.
CLI failure is fixed/redacted and Uvicorn's own traceback loggers are silenced.
The default provider gate remains false; signed health cannot claim readiness or
allow model work. No environment backend selection or uncertain Action replay.

New separately prepared hardened `shopping-copilot-agent.service` conflicts with
the legacy combined unit; legacy runtime unchanged. Both are packaged in fresh
immutable releases; neither new unit installation nor activation occurred. It
supervises Agent only. Full Storefront/Caddy supervision and real target-host
POSIX/key/config/systemd/signal/shutdown acceptance remain open.

TDD missing-module/unit RED then20passed6.01s. Final host tests84passed27.17s,
including actual Uvicorn lifespan/bind failures without opening sockets, closed
qualification/no model call or ledger change, loop refusal and SDK close-once.
Broader all-Agent/host/control/package/access/waiting/fresh-release/browser suite
1066passed/no skips297.79s; it collected before the two additional actual-Uvicorn
cases, both included in final84host checks. Ruff check/format249files, pip check,
TypeScript lint, changed Markdown/JSON Prettier and whitespace pass. Fresh final
review clear; independent84host tests23.91s. Two upstream websockets deprecation
warnings in real-Uvicorn host checks, no failures. Evidence:
`eval/evidence/cap06-host-launcher-20261023.json`; guide:`docs/cap06-host-launcher.md`.

Next: complete inactive Storefront/Caddy host orchestration and protected Linux
host configuration acceptance, then reconcile observation inventory/cost/credit
proposal. Final resource/cost/rollback approval, effective IAM/OAC/event/account
access, Bedrock quotas/qualification, deployment and cloud acceptance remain open.
No real AWS/model/credential/resource/key/DNS/TLS call/write, upgrade, activation,
extra spend or push. Free-plan/Stockholm/zero-cash and all open gates persist.

## CAP-06 inactive external observations prepared — 2026-10-22

Prepared a reviewed browser-independent lifecycle design and current primary AWS
research. Proposed addition: one Stockholm EventBridge Scheduler schedule/group/
scoped execution role targeting the existing controller every minute, finite UTC
window, flexible window OFF, no delivery retries and60second delivery/async age.
No third Lambda, SQS/SNS, public endpoint or runtime schedule-admin permission.
Exact internal tick reads current generation, observes first, then attempts at
most one already-pending command with existing fresh invitation/deadline/claim
fences. It never creates wake intent, extends activity or replays unknown work.
Successful tick-only bounded EMF completion metric plus missing-completion/error
alarms prevent browser traffic masking absent observations; no notification action.
Controller tick/runtime/entry and deploy/observation.py pure configuration are
implemented and tested locally under the owner's continuation, never activated.
The schedule always renders DISABLED and alarm actions false. Tick failures cross
both generic wrappers as a fixed redacted error for Lambda Errors; initialization
stays latched. Browser dispatch/observe events keep their existing contract.

Public Free-project policy includes scheduler actions as exceptions to one deny;
that is not account permission. Spend-limit policy can deny CreateSchedule.
SourceArn trust must bind the schedule GROUP. Actual account/credit/concurrency
eligibility remains unverified. Gross Stockholm Scheduler86400ticks=$0.094176;
full conservative scenario includes256MiB/30s Lambda,160RRU/144WRU per tick,
logs/storage/one custom metric/two alarm metrics:USD22.1716576, rounded22.18.
Proposed additional planning allocation23 brings previous55.50reference to78.50,
leaving1.50inside proposed80 plus separate20unallocated from last evidenced100.
No free allowance subtracted; real duration/billing/traffic remain unmeasured,
INIT/duplicates/extra requests can exceed assumptions. This consumes most
prior contingency and is neither a spending cap nor new spending authorization.

Design:docs/superpowers/specs/2026-10-22-cap06-observation-delivery-design.md;
sources:docs/research/2026-10-22-cap06-observation-delivery-contract.md. Fresh builder
check found nothing important unanswered; primary separately verified core AWS
policy/trust/async contracts and Decimal arithmetic. Local RED/GREEN stopped/
lost-notification/duplicate and concurrent claim/revocation/expiry/deadline/late-
cleanup/unknown-command/lease/activity races, tick-only metric/redacted failure
and disabled renderer tests36passed11.40s. Independent final review clear;
108focused/previous controller-entry-runtime tests33.72s. Instrumented profiles:
stopped3Get/no write; unclaimedSTART26Get/3transactions;128live leases6868byte
largest DynamoJSON item; cold construction adds4Get. These fit scenario assumptions,
not actual billing/capacity guarantees. Both updated role ZIPs rebuilt identically
and passed isolated Windows3.12 -I -S -B import/fixed-role/error checks, SDK/network
blocked. Guide:docs/cap06-observation-delivery.md. Final all-Agent/observation/
package/host/access/browser/fresh release build1036passed/no skips170.67s; Ruff
check/format247files, pip, ESLint, Prettier and whitespace pass. Evidence:
eval/evidence/cap06-observation-delivery-20261022.json. Updated startup ZIP
25888663bytes SHA2567d90b216b33f4697354df220764e8a2f79dd35b63bcc1fff2e2c01f72aac5f7d;
controller25888669bytes8b968e9daf2d9cb0a8191eec0a5d5a3d9945ebe7d82b10e08707760332b5c641.

Next: exact artifact AL2023 execution, host launcher integration, and reconciliation
of this explicit new-service/cost/credit proposal. No service is added to selected
inventory yet. Actual AWS
apply retains separate full resource/cost/rollback approval; AL2023 execution,
host launcher/POSIX/key/config/IAM/OAC/event/account checks and Bedrock qualification
remain open. No real AWS/model/credential/resource/key/DNS/TLS call/write, upgrade,
activation, extra spend or push. Free-plan/Stockholm/zero-cash invariants persist.

## CAP-06 reproducible Lambda ZIPs prepared — 2026-10-22

Added fixed-role lazy Lambda entries and an offline narrow wheel/ZIP builder.
Exactly14 pure Python dependencies are pinned by version/filename/SHA256 with a
matching pip hash lock. Builder verifies metadata/tags/Python3.12 compatibility,
no-extra Linux dependency closure, all RECORD hashes/sizes, paths/links/collisions
and size limits. Only explicit control modules and waiting.html enter the ZIP;
no credentials/config/keys/local state/dev/native/bytecode files. JMESPath's one
unused standalone CLI is verified then explicitly omitted and recorded. SDK data,
CA certificates, licences and metadata remain. Fixed timestamps/sorted members/
POSIX modes/ZIP_STORED produce byte-identical rebuilds. External retained ZIP
digest is required for verification; manifest hashes alone are not authenticity.

Generated handler.handler pins startup/controller role. Bounded exact version1
runtime JSON and separate canonical controller key validate before SDK creation;
import creates no clients. First-invocation initialization is cached or latched
unavailable after failure; events cannot switch roles, invocation failure never
reconstructs/replays runtime. Generic errors disclose no configuration/key.

Both actual packages independently rebuilt/verified by primary and fresh reviewer,
then passed Windows Python3.12.5 -I -S -B imports/delegation with SDK/network
forbidden, dependency provenance/versions and service models/CA checked. Startup
25,886,261bytes SHA256 88c5f11d3e6770091146a196c4a3a58ece4774ce6a08b4c4a29b57dd25f65661;
controller25,886,267bytes e208482f62b7a3158766fe59d63be86c47b6e2cb21a9aa2a560b70c6f4248ad0.
Fresh review clear; focused64passed3.76s (independent64passed5.05s); final all-Agent/
package/host/access/browser/fresh release build1000passed/no skips161.48s. Ruff
check/format244files, pip, ESLint, Prettier and whitespace pass. Evidence:
eval/evidence/cap06-lambda-package-20261022.json; guide:docs/cap06-lambda-package.md.

Next: reliable approved external observation delivery and deployment integration.
Exact artifact AL2023/architecture execution, runtime configuration/key provisioning,
host launcher selection/POSIX acceptance, effective IAM/OAC/event/account eligibility
and final resource/cost/rollback approval remain required. Windows proof is not
Linux execution or deployed acceptance. No AWS/model/credential/resource/key/DNS/
TLS call/write, upload, activation, upgrade, scheduler/topology/spend increase or
push. Public PyPI wheel acquisition only, followed by offline target/hash validation.
Bedrock zero quotas, Free-plan/Stockholm/zero-cash and all open gates persist.

## CAP-06 restricted host startup API prepared — 2026-10-22

Added deploy/host_config.py strict bounded version1 JSON, immutable validated
HostSettings, separate private raw key files, generic errors and no secret repr.
Default reader is POSIX-only: protected owner/mode/parents, no-follow/nonblocking
open, one link, stable bounded fstat/read. Windows refuses default loading; local
trusted-reader/metadata tests do not prove real Linux permission enforcement.

deploy/host_bootstrap.py explicitly assembles existing remote authority, one
GuardedClient, owned work/admission/service and concrete signed readiness. It
refuses active event loops and wrong executing release root before SDK creation.
No environment/CLI/systemd activation. create_app now accepts copied explicit
environment through identity/mode/retrieval/encoder selection, without dotenv/
local-identity fallback or environment mutation. Legacy app attribute is lazy;
import alone constructs no default app. Private async identity and synchronous
Confirmation calls disable environment proxies. Default unqualified provider
blocks requests/model entry and inference charging even with stale healthy=true;
owned stop and pending renewal remain available. No pass format/fallback invented.

Review reproduced/fixed ambient setting gaps, Confirmation proxy path, provider
await holding the lease actor lock, and cancelled shutdown closing shared SDK too
early. RED/GREEN moves a bounded one-flight1s verifier outside the actor; final
remote/local authority fences follow it. Retained cancellation-resistant close
drains lifecycle and admission workers before SDK close once off-loop. Review
clear; final shutdown checks independently2passed3.15s. Final all-Agent/host/config/
bootstrap/access/browser/fresh artifact build936passed/no skips145.06s; focused
environment/bootstrap19passed9.41s. ESLint/Prettier, Ruff check/format239files,
pip and whitespace pass. Evidence:eval/evidence/cap06-host-bootstrap-20261022.json;
guide:docs/cap06-host-bootstrap.md. Existing launcher/backend remains unchanged.

Next: Linux Lambda dependency packaging, approved reliable external observation
delivery and deployment integration. Real POSIX/key provisioning and execution
from installed release (-B interpreter), selecting the host API in launcher,
effective IAM/OAC/event/account eligibility and final resource/cost/rollback
approval precede deployed acceptance. No real AWS/model/credential/resource/key/
DNS/TLS call/write, upgrade, scheduler/topology/spend increase or push. Bedrock
zero quotas, Free plan/Stockholm/zero cash and all open gates persist.

## CAP-06 concrete host readiness checks prepared — 2026-10-22

Added deploy/host_checks.py: concrete pinned release integrity, authenticated fixed
private catalogue/revision, remote admission metadata and funded durable allowance
checks for the existing signed-health hook. Release/SQLite work is off-loop with
two workers/eight retained calls. Private HTTP has no proxy/redirect/retry/cache,
identity encoding,32768raw-byte cap, duplicate-JSON refusal and1sasync timeout;
local catalogue revision/content is rechecked after I/O. Authority/service/guard
bindings are pinned and revalidated. No grant/session/activity write, allowance
reset/enable/reservation/refund or unknown-charge release. Allowance observation
requires maximum supported guarded request headroom; real requests still arbitrate.

Provider verifier remains explicit: unqualified_provider returnsFalse for today's
blocked Bedrock candidate. Four successful checks cannot sign ready with this
binding. No new qualification artifact/pass format, fallback or gate waiver.
Actual restricted configuration/key loading, startup and lifetime wiring remain
pending; caller drains health, checks, then work/admission/service. This tests the
authenticated catalogue service, not all shopper journeys or process supervision.

RED/GREEN metadata seam and concrete checks; valid cloned admission-store rebinding
reproduced/refused. Fresh review clear:32concrete/boundary and19existing host checks
passed independently. Final all-Agent/concrete/access/browser/fresh artifact build
894passed/no skips139.37s; focused32passed11.09s. ESLint/Prettier, Ruff check/format
234files, pip and whitespace pass. Evidence:
eval/evidence/cap06-host-checks-20261022.json; guide:docs/cap06-host-checks.md.

No AWS/model/credential/resource/key/DNS/TLS call or write, backend activation,
upgrade, scheduler/topology change, spend increase or push. Next: restricted
host bootstrap and Linux Lambda package; costed approved reliable observation
delivery, effective IAM/OAC/event eligibility and final resource/cost/rollback
approval precede deployed acceptance. Bedrock zero quotas, Free plan/Stockholm/
zero cash and all open gates persist. Local fixtures do not establish qualification.

## CAP-06 async host authority and signed health integrated — 2026-10-22

Explicit Agent factories now support async remote admission/work and signed host
health. Remote datastore I/O runs in retained bounded workers; owner/session
bindings are revalidated after waits. Work pins one generation, transfers accepted
protection to pending Tasks through degraded health, fences failed renewal or
generation changes and never resurrects expired authority or replays Actions.
Unknown writes retain counters/finite orphan protection; close drains known work.
Only successful explicit interactions advance activity. Default backend unchanged.

Signed health requires five explicit trusted async checks and valid HMAC before
I/O. No default ready=true or actual provider qualification. One aggregate slot
retains slow cancellation cleanup after a1.5second false response. Final remote
state and synchronous local failed/closed/generation fences protect signing.
Lifespan drains health, work, admission and service, including startup failure.

Fresh review found slow cancellation exceeding the response deadline and a local
failure race across aggregate completion; both reproduced RED and fixed GREEN.
Review clear:21host/original-repro checks8.06s plus5mock concurrency checks6.29s.
Broad verification exposed Moto whole-table rollback erasing competing winners;
deterministically reproduced and fixed only in the test fixture's atomic datastore
operations. Workflow races/shared-revision barriers and production CAS stay intact.
Final all-Agent/access/browser/fresh release build865passed/no skips119.85s;
focused remote authority/executor/host96passed36.94s. Lint/format/pip/whitespace
pass. Evidence: eval/evidence/cap06-host-boundaries-20261022.json; guide:
docs/cap06-host-boundaries.md. No AWS/model call, resources, keys, DNS/TLS writes,
environment backend activation, upgrade, spend authorization increase or push.

Next: actual trusted host checks/bootstrap and restricted configuration/key
loading, Linux Lambda dependencies and approved reliable external observation
delivery. Injected callbacks alone do not establish deployed readiness. Browser
polling/future host heartbeats alone do not guarantee idle/outage scheduling; no
new scheduler/sleep/self-invocation adopted. Effective IAM/OAC/event eligibility,
resource/cost/rollback approval and deployed acceptance remain open. Bedrock zero
quotas, Free plan/Stockholm/zero cash and all existing gates persist.

## CAP-06 runtime factories and trusted readiness prepared — 2026-10-22

Added explicit injected startup/controller factories, role-bound settings, bounded
async Event notifier and fixed-instance observer/worker. Accepted wake records its
intent then queues dispatch; status can queue observe, which may claim only STOP.
Strict operation/generation filters apply inside the durable claim snapshot.
Duplicate/stale events cannot replay a claimed command or affect a newer generation.
Unknown queue acknowledgement retains intent and returns generic503; no app retry.

Fresh HMAC readiness binds random nonce, expected release.json SHA-256, generation
and strict ready bit. Fixed verified HTTPS, no proxy/redirect, bounded streaming;
ordinary /health liveness and invalid/stale proofs never mark ready. Host reply
helper remains inactive until real service/catalogue/admission/allowance/provider
readiness and async work integration. No production key generated or supplied.
EC2 uint16 state validation now ignores documented internal high byte in both
observer and executor. Captured revision/generation fences external observations.

Independent review reproduced readiness rechunking delaying the deadline through
1025slow subchunks; RED regression, raw per-chunk checks, GREEN. Reviewer now stops
at two chunks/two simulated seconds and reports clear with93checks23.09s.
Final admission/lifecycle/allowance/runtime/access/browser and fresh release build:
308passed/no skips94.71s. ESLint/Prettier, Ruff check/format225files, pip and
whitespace pass. Evidence: eval/evidence/cap06-controller-runtime-20261022.json.

No AWS/model call, resource/policy creation, DNS/TLS write, key provisioning,
environment-selected backend/provider activation or push. Default SDK builder is
lazy/explicit, fixed Stockholm endpoints with TLS/proxy/retry bounds; tests inject
Moto, Stubber and HTTPX MockTransport with dummy credentials. Guide:
docs/cap06-controller-runtime.md; cited AWS async/state research linked there.

Next: real host readiness/async work integration, Linux Lambda package/bootstrap
and costed approved reliable observation delivery. Browser polling/future host
heartbeats do not prove outage/idle scheduling; no new service or sleep/self-loop
was silently added. Concurrency/event configuration/account-effective IAM and
approved resource/cost/rollback deployment precede cloud acceptance. Bedrock zero
quotas, Free plan/zero cash and all open gates persist; automatic wake/stop is not
deployed or accepted.

## CAP-06 CloudFront/Lambda access and viewer signing prepared — 2026-10-22

Added pure deploy/cloud_access.py: frozen exact-resource bindings render separate
startup/controller runtime policies, both required Lambda Function URL grants,
exact-distribution OAC, waiting-prefix S3 access and uncached custom origin header
forwarding. Startup has no EC2 grant; controller start/stop is fixed-instance and
DescribeInstances is region-bound. DynamoDB uses GetItem plus transaction-only
PutItem/UpdateItem/ConditionCheckItem with exact table and namespace; no fictitious
TransactWriteItems IAM action or runtime initialization permissions. Own precreated
Lambda log streams only, seven-day retention handoff. No actual identifiers chosen.

AWS primary-source research found viewer POST requires x-amz-content-sha256 for
Lambda OAC. Shared waiting.html now hashes the exact UTF-8 JSON body with Web
Crypto and sends that same body; hashing failure sends no POST. Browser tests
intercept all requests on synthetic HTTPS and localhost with nonce CSP, verify
the digest with Python hashlib and preserve input cleanup/fixed links/no storage.

Builder/review clear, independently28focused tests passed in3.78s. Final affected
local/remote lifecycle/startup/executor/access/browser suite and fresh release
build:159passed/no skips68.92s. ESLint, Prettier, Ruff check/format219files, pip
and whitespace pass. Evidence: eval/evidence/cap06-cloud-access-20261022.json.
Guide: docs/cap06-cloud-access.md; cited AWS contract research linked there.

This JSON bundle is not a deployable stack, effective IAM authorization result
or deployed OAC test. No AWS API/model call, policy/resource creation, DNS/TLS
request, upgrade, active backend/provider change or push. Next: actual Lambda
factory/package, controller readiness/observation scheduling, fixed host and async
Agent work integration, then approved deployment and cloud acceptance. Final cost
estimate must count controller invocations and DDB operations. Bedrock zero-quota,
Free-plan/zero-cash constraints and all open gates remain unchanged.

## CAP-06 single command executor and startup HTTP prepared offline — 2026-10-22

Added injected agent/lifecycle/executor.py and startup.py. The executor claims one
pending intent, refreshes exact authority/deadline and bounded Stockholm client
policy, then attempts at most one StartInstances/StopInstances operation for its
fixed configured instance. Validated acknowledgement still requires trusted host
observation. Service errors, lost/malformed replies and failed settlement never
cause automatic retry or claim takeover. DynamoDB generation is not an EC2 fence.

The HTTP-v2 handler serves the existing waiting UI for a configured generated
CloudFront HTTPS origin, exposes only safe status and accepts bounded same-origin
JSON wake requests. It never dispatches EC2, redeems shopping access or extends
activity. Three persistent conditioned rate lanes240/10/120per minute fail closed
on conflicts, rollback, corruption and uncertainty. Permanent metadata markers
prevent deleted rate rows from reopening as unused. No event/code/SDK logging.

Fresh independent review and RED regressions reproduced two pre-dispatch timing
gaps: invitation I/O could cross the deadline, and client policy could change
during authority I/O. Final deadline/client checks now follow those reads.
Review clear; independently114passed. Final broader admission/lifecycle/allowance
regressions plus fresh self-contained release build:211passed/no skips in82.78s.
ESLint, Prettier, Ruff check/format216files, pip and whitespace checks pass.
Evidence: eval/evidence/cap06-command-startup-20261022.json.

Tests use dummy credentials, Moto DynamoDB and stubbed EC2 only. Moto concurrency
tests serialize simulated server transactions to compensate for its nonisolated
backup/rollback implementation; real AWS concurrency/IAM/durability remain
unverified. No AWS/model call, actual EC2 command, resource/table/instance creation,
DNS/certificate request, upgrade, provider/backend activation or push occurred.

Next: Lambda/OAC/IAM and fixed instance wiring, trusted readiness/observation
scheduling and async Agent/host work integration, then approved deployment and
cloud acceptance. Public cost bounds, zero cash and Free-plan constraints persist.
Bedrock zero quotas and all open acceptance gates remain blockers; these prepared
components do not establish deployed automatic wake or cloud readiness.

## CAP-06 remote lifecycle decisions implemented offline — 2026-10-21

Added agent/lifecycle/dynamodb.py: durable wake generation, revision-bound health
observations, meaningful activity,128bounded work leases, idle drain/stop commitment
and single-use command claim/completion. Transactions bind lifecycle identity/
revision, invitation metadata and current startup invitation validity. Explicit
initialization permanently records lifecycle_identity in metadata so deleting the
host item cannot reinitialize/reset an outstanding command fence.

Claimed/uncertain commands never expire into a new dispatcher. Timeout plus an
observed stopped host cannot unlock a claimed command. Certain late start requires
cleanup stop; certain stop acknowledgement plus observed stopped precedes restart.
This is a persistent handoff protocol, not actual EC2 API fencing: no EC2 callback,
executor or public HTTP/factory selection is included. Unknown outcomes remain
locked for owner investigation; no automated unlock/replay path exists.

Fresh review reproduced unhealthy idle drain admitting new work: RED regression,
persisted strictly validated health independent of drain, GREEN, reviewer clear.
Accepted leases still renew under degraded health. Additional RED/GREEN regressions
cover deleted-state reset, inconsistent command/state, post-claim revocation,
invalid lease tokens, future activity timestamps and malformed host observations.
Independent reviewer39corechecks passed; final suite includes40remote lifecycle
checks plus remote/local invitation/lifecycle/inference regressions and fresh
self-contained release build:139passed/no skips in58.83s. Repository lint/format,
pip and whitespace checks pass. Evidence:
eval/evidence/cap06-remote-lifecycle-20261021.json. Existing runtime factories,
local SQLite lifecycle, base dependency lock and provider remain unchanged.

Next: separately tested single command executor/outcome protocol and bounded
startup/status HTTP, then Lambda/OAC/IAM and async Agent/host readiness integration.
No AWS/model calls, resource/table/instance creation, actual EC2 command, DNS,
certificate request, upgrade, active backend/provider switch or push. Real AWS
conflicts/IAM/durability/costs, public TLS and deployed acceptance remain unverified.
Bedrock zero-quota blocker, disabled diagnostic allowances and all open acceptance
gates persist. No cloud readiness or completed automatic-wake deployment claimed.

## CAP-06 remote invitation adapter implemented offline — 2026-10-21

The first remote invitation/wake-control component is implemented in
agent/admission/dynamodb.py. It preserves absolute invitation windows, hash-only
codes/subjects, cumulative redemption/session limits, revocation and same-grant
idempotence in bounded conditioned DynamoDB transactions. Wake validation grants
no shopping/session authority. Explicit initialization refuses nonempty/orphaned
namespaces; runtime never initializes. Strong reads refresh identity each operation;
uncertain writes do not retry or refund. Fresh validation rejects expired/revoked
post-write authority while retaining committed counts.

Existing SQLite factory/configuration and active model provider are unchanged.
This is an injected, offline-tested backend, not a deployed or selected service.
Optional Moto5.2.4 extras are pinned separately in eval/requirements-cloud.txt;
base runtime locks unchanged. Real Boto3 calls are intercepted with dummy
credentials in-process; no AWS account API/table or local listener was used.

Final adapter40tests pass/no skips. Focused admission/lifecycle/allowance and fresh
artifact build99passed/no skips in39.96s. Full release/proxy subset14passed in148.42s
before the final status-only fix; the final99checks rebuilt the latest module.
Independent reviewer found malformed query records could masquerade as healthy
status rows: reproduced RED, fixed with shared validation of each actual row,
rechecked clear. Other RED/GREEN fixes cover strict schema/client bounds,
post-write revocation and changed invitation limits. Evidence:
eval/evidence/cap06-remote-invitations-20261021.json.

Next: remote lifecycle generation/work-lease/stop arbitration and safely fenced
host commands, then Lambda/OAC and async host integration. Earlier wake reads
must not independently authorize EC2: invitation validity belongs in the same
atomic wake decision. No resource provisioning, DNS, paid inference, quota reset,
provider switch, upgrade or public exposure. Bedrock zero-quota blocker, disabled
diagnostic allowances and remaining CAP-04/05/06/07 gates stay open.

## CAP-06 public HTTPS configuration prepared — 2026-10-21

Owner said continue with local deployment preparation while Bedrock is blocked.
Added deploy/Caddyfile.public for exactly app.scpilot.tech/store.scpilot.tech:
explicit Let's Encrypt ACME, fixed loopback upstreams, external persistent Caddy
state, strict SNI/Host and HTTP/1.1+HTTP/2. Existing deploy/Caddyfile is unchanged.
Public profile routes/log redaction match the existing parsed rehearsal contract;
legacy host/bind/upstream/static-certificate overrides cannot change its identity.

Both profiles now ship in the hashed release. A modified installed public profile
fails verification. Neither the existing runtime nor service launches/selects the
public profile. The template does not validate external state paths/ownership or
build-origin correspondence; those require the eventual host preflight/service.

TDD: four missing-profile failures before implementation. Final real-Caddy and
release run:14passed,0failed,0skipped in148.60s; actual artifact builds and scripted
restart/browser checks preserve uncertain Action, invitation and allowance state.
Fresh-context review clear, independently3adapt tests passed with no skips.
Repository ESLint/Prettier and Ruff check/format pass; Caddy canonical bytes,
unchanged rehearsal config and whitespace checks pass. Evidence:
eval/evidence/cap06-public-https-20261021.json; plan:
docs/superpowers/plans/2026-10-21-cap06-public-https-preparation.md.

No AWS/model calls, certificate requests, DNS writes, public listeners, provider
switch, account upgrade or push in this slice. Adaptation parses only; no module
provisioning, public TLS/renewal/redirect or cloud-browser qualification is claimed.
CAP-05, remaining CAP-04 feasibility and CAP-06/07 acceptance stay open. Next local
work is the remote invitation/lifecycle authority contract and host preflight;
resource/IAM apply, DNS, trusted host readiness and live qualification retain their
gates. Preserve both consumed diagnostic claims and disabled allowances.

## Second diagnostic executed; zero applied quotas — 2026-10-20

The owner separately approved one additional call with at most USD0.02 AWS credit
use. Exactly one further Converse attempt used the same frozen ar-01 request and
zero retries. It failed after 703ms with ThrottlingException / HTTP429; no output
or usage returned. The first attempt's exact service error remains unknown.

Read-only applied Service Quotas show GPT-OSS20B on-demand requests/minute=0 and
tokens/minute=0 in Stockholm. Nova Lite's on-demand requests/minute, tokens/minute
and daily tokens are also zero. Positive availability and ACTIVE/ON_DEMAND model
metadata do not override these account quotas. The zero allocation is an observed
blocker; its account-specific reason is unknown. No quota increase was requested.

Both exclusive claims are consumed and both diagnostic ledgers are DISABLED.
Each retains USD0.015 with one uncertain attempt: USD0.03 held across two attempts,
against USD0.04 cumulative authorization. Actual billed costs remain unknown;
unused balances do not authorize another call. No third call or full set is
approved. No provider switch, upgrade, subscription, deployment or DNS change.

Sanitized second result and applied quotas are in
eval/evidence/cap05-diagnostic-20261020/second-result.json and quotas.json. The
original first result is unchanged. Private plans/claims/ledgers stay in their
separate ignored outputs/cap05-bedrock-diagnostic-001/ and -002/ directories.

AWS documents zero quotas as a possible account restriction; no guaranteed
self-service Free-plan activation or evidenced Paid-upgrade fix was found. GPT-OSS
needs no Marketplace subscription. Support is currently unreachable; do not keep
asking for the same owner response or infer that waiting resolves it. See the
applied-quota section of docs/research/2026-10-20-cap05-access-preflight.md.
Keep CAP-05 and parent acceptance gates open. Further offline preparation may
continue within approved scope; any provider/API change requires an explicit
scope decision and subsequent qualification.

### Read-only continuation check — 21 October 2026

A two-quota GET recheck stopped at LoginRefreshRequired before obtaining fresh
quota data; no inference was attempted and no account setting changed. The
20 October zero-quota observation remains the latest verified allocation, not a
claim about a refreshed 21 October value. Do not request another browser sign-in
solely to repeat this known blocker. Next permitted independent work is local
CAP-06 preparation from docs/cap04-deployment-handoff.md; provisioning and live
qualification retain their gates.

## Historical first diagnostic and second-call proposal — 2026-10-20

Owner explicitly approved one diagnostic with USD0.02 maximum AWS credit use.
Exactly one Converse attempt ran from the frozen ar-01 request. Provider HTTP
failure after1313ms; no output/usage or exact service code captured by that revision.
Actual billed cost is unknown. Full USD0.015 reservation retained; one uncertain
attempt, USD0.005remaining; the owner-controlled ledger is now disabled and the
exclusive claim remains consumed. Do not reset/retry, silently use remaining
allowance, or infer zero billing. No full qualification set is authorized.

Read-only GetFoundationModel reports ACTIVE and ON_DEMAND. CloudTrail history
initial checks found no matching Converse event; no cause established. No logging
configuration enabled, agreement change, deployment or upgrade. Positive model
availability remains evidence of eligibility only. Sanitized preserved failure:
eval/evidence/cap05-diagnostic-20261020/; private claim/ledger/result and correlation
remain under outputs/cap05-bedrock-diagnostic-001/.

Offline follow-up retains allowlisted AWS service codes and strict HTTP status in
future metadata, never raw error bodies. Two tests observedRED thenGREEN;41adapter
and77combined focused checks pass. Independent review clear. This telemetry fix
does not explain/fix the failed request or authorize replay. Earlier full-suite
754pass/1timeout plus three successful serial reruns remains the full evidence.
Final read-only trace around307seconds saw surrounding events but no matching
inference request. Diagnostic002 is prepared in its separate owned directory,
identical request hash and binding to the first result. It proposes one additional
call/USD0.02credit (USD0.04total across both), pending explicit approval. First
claim/disabled ledger/held reservation stay untouched; no fullset/third call. All parent
CAP04/local02/final09/liveCAP05 acceptance gates remain open.

## CAP-05 account/model eligibility verified — 2026-10-20

Owner CloudShell GET and an independently executed local Boto3 GET both report
AUTHORIZED plus AVAILABLE agreement, entitlement and Region for the Stockholm
openai.gpt-oss-20b-1:0 candidate. This is actual read-only availability evidence,
not invocation/quality/quota/billing proof. Current-user AWS CLI2.38.2 was installed
from the official MSI after valid AWS/DigiCert signature verification; owner
approved the browser login for cap05-stockholm. Optional boto3[crt] support adds
awscrt0.36.0, pinned in eval/requirements-bedrock.txt. No access keys were shared.
CloudShell has ordinary AWS-managed environment/home state; no application
infrastructure, upgrade, DNS change or model call occurred.

Single-call preparation: eval/bedrock_diagnostic.py defaults to a frozen dry plan,
fixed exposed ar-01 case/current prompt/schema, one Converse attempt/no SDK retries,
exclusive nonresetting claim and USD0.015 retained reservation inside a proposed
USD0.02 credit allowance. It checks the actual request hash after credential
initialization and before provider entry; independent review caught this race,
RED/GREEN regression and recheck clear. Eight diagnostic /75combined focused tests
pass. No runtime application changes; retain the earlier full754pass/1timeout and
three unchanged successful reruns rather than claiming a new full-green suite.

See docs/cap05-diagnostic-protocol.md and dated execution plan. Paid diagnostic
approval is pending; do not infer permission from go, old OpenRouter approvals
or the architecture allocation. Local02/final09/parentCAP04 and liveCAP05 stay open.
Public IPv4 coverage and other resource permissions remain unresolved.

## CAP-05 offline adapter slice implemented — 2026-10-20

Owner authorized the offline Bedrock slice after the conditional handoff. Candidate
Stockholm openai.gpt-oss-20b-1:0 uses Converse behind the existing LLMClient; active
provider/configuration and OpenRouter cap are unchanged. See docs/cap05-bedrock.md
and dated design/plan. SDK construction is lazy, zero retries; cancellation drains
provider work before releasing the guarded slot. Metadata is bounded/redacted;
unknown costs retain reservations and configured prices must meet the dated floor.
Shared canonical schema expansion fixes reference-sibling under-reservation;
leading assistant history is preserved through a fixed context marker. Independent
review found these two edge cases; both have RED/GREEN regressions and clear
recheck. Standards review clear.

39 Bedrock tests and 79 combined focused checks pass. TS199/build/Panel types/
ESLint/Prettier/Ruff check/format and pip check pass. Full Python/browser result:
754 passed, 1 failed in 761.94 seconds, two upstream WebSocket warnings. One
Franco-Arabic discovery case exceeded its unchanged 10-second deadline; the same
seven-case test passed three serial reruns without code changes. Root cause is
unestablished; do not claim the original full run was green or a product bug was
fixed. Durable ignored logs/results: outputs/cap05-bedrock-verification/.

No AWS account credentials, model calls, resources, DNS or provider switch.
Local02/final09/parentCAP04 and liveCAP05 remain open. Next: reconcile account/model
eligibility, qualify cost/token/schema semantics and obtain a concrete bounded
live-call authorization before strict CAP05 and separate unseen-set evaluation.
Offline token metadata is not a verified USD receipt or model-quality evidence.

## Continue without Support response; conditional handoff — 2026-10-20

The owner could not reach Billing Support and explicitly instructed continuation
with the available evidence. Do not keep asking for the same Support response.
Public IPv4 credit coverage remains unknown; no service permission or cash-charge
acceptance is inferred. Free plan/USD0 cash, existing provider cap, separate paid
qualification and resource/DNS authorization remain in force.

The consolidated package is docs/cap04-deployment-handoff.md: selected topology,
service/state inventory, trust/IAM/secrets, retained certificate and allowance
state, dated all-in costing, release/rollback/teardown and CAP-05/06/07 checks.
Local02 remains open; local09 preparation may proceed under this owner exception,
but final09/parentCAP-04 acceptance is not claimed. Offline Bedrock adapter and
infrastructure preparation are the next actionable work; live qualification and
provisioning remain separate. No runtime, account, resource, DNS or model changes.

## Virginia restriction; generated-host wake selected — 2026-10-19

Owner screenshot explicitly confirms ACM Virginia is unavailable, the project is
assigned to Stockholm, and other commercial Regions require upgrade then advanced
features. This supersedes inference from generic managed-policy exceptions. No
API issuance workaround or account upgrade is authorized. Lambda, DynamoDB and
Stockholm ACM landing/list visibility are recorded; action authority remains a
separate check.

The owner chose automatic wake through a generated CloudFront HTTPS hostname,
with direct Caddy public ACME HTTPS for app.scpilot.tech/store.scpilot.tech. See
the [approved amendment](docs/superpowers/specs/2026-10-19-cap04-stockholm-ingress-amendment.md).
Only waiting/control uses CloudFront; cold entry requires that generated link.
A direct shopping bookmark does not wake a stopped host. No shopping cookies or
Action authority move across sites; code reentry remains required. The two custom
shopping origins, safety invariants and restart semantics are unchanged.

The verified-rate direct-plus-wake reference is approximately USD26.99 at 120
running hours / USD55.50 continuous over 60 days including USD11 model/qualification
allocation; no new spending permission. Builder review found no important unanswered
owner design questions. Local 02 remains open for account/credit/feature and DNS
editing evidence; 09 and parent CAP-04 remain open. Owner DNS Records screenshot now confirms Add new record and A/CNAME controls with no purchase prompt visible; no records saved. Credit screenshots list Bedrock, Elastic Compute Cloud, Lambda, DynamoDB, S3, CloudFront and CloudWatch. Stockholm VPC dashboard/list open: one Available VPC, three subnets, zero NAT gateways and zero Elastic IPs; default status not inferred. Both Virtual Private Cloud and VPC searches return no match; public IPv4 coverage remains unresolved. Individual credit starts 7 October 2026 and expires 7 October 2027 at 15:41 UTC, distinct from Free-plan end 7 April 2027. Listed credit applicability is not resource authority, and the later expiry does not extend Free-plan access. Independent Spec review cleared the amendment; Standards historical-next-step wording corrected.
No production code, resources, certificates, DNS writes, model calls or paid upgrades.

## Account feasibility refresh — 2026-10-19

Latest owner screenshots: Lambda, DynamoDB and ACM landing pages open. Generic Virginia ACM deep link reaches a blank sign-in/session-selector redirect, not an access-denied response. The subsequent ACM certificate list loads with zero entries; its cropped screenshot does not expose Region. Owner then supplied the working URL confirming eu-north-1 Stockholm. Virginia list access remains unverified; next navigation diagnostic preserves the working account/session prefix and path while changing only the hostname Region. No request/creation or account/browser-security changes.

Continuing local Ticket 02 after local 08 closure. Fresh owner screenshots show
Free-plan cost/usage wording, USD100.00 remaining, USD0.00 current-month cost,
171 days remaining and plan end 7 April 2027. Additional activity credits show
USD0 of 100 earned, 0 of 5 completed. Do not count advertised USD200 or create an
unneeded RDS/playground workload to collect rewards. The owner subsequently supplied explicit Free-plan Billing evidence, USD0 due, project-based menus and a console URL selecting eu-north-1 (Stockholm). Project home-Region confirmation, individual credit expiry/applicability, service/model entitlement and DNS-editing access remain pending. See [account evidence ledger](docs/cap04-account-feasibility.md).
No AWS CLI/config/credentials found locally; no authenticated AWS API audit,
resources, model calls or account changes occurred. Account-specific evidence is
requested from the owner. Bedrock catalogue and gpt-oss-20b details plus the CloudFront dashboard now open normally (owner evidence), not proof of Invoke/Create authority. Official-source Stockholm cost scenarios and independent Decimal recomputation are recorded in docs/research/2026-10-19-cap04-network-cost-refresh.md. The continuous CloudFront/main-delivery/wake scenario rounds to USD57.20 under its explicit workload; no fresh AWS inference spending permission is implied. Local 02/09 and parent CAP-04 stay open; original checkout
and the existing OpenRouter cap/configuration remain untouched. Independent Spec/Standards reviews corrected a circular deployed-acceptance prerequisite and a stale handoff sentence. Decimal arithmetic, Markdown formatting, source-only path/credential checks and diff checks pass; no application changes require a new full regression run.

## Physical Android passed; local Ticket 08 resolved — 2026-10-18

The remaining local hardware gate passed on the owner's CMF Phone 1 (A015),
Chrome155.0.8059.41. One physical phone plus four independent desktop contexts
completed five cart mutations, with foreign-session 404 denials both ways and
phone refresh without another cart POST. A held eight-desktop burst plus an
additional phone request demonstrated four safe queue refusals, unchanged phone
cart and exactly five further fixture calls. Total physical-experiment calls10,
paid calls0. Evidence and exact limits: [capacity runbook](docs/cap04-capacity.md),
ignored outputs/cap04-capacity-android-001/. No production source changed after
the verified automated slice b5bccfc: full716 Python/browser tests, TS199,
builds/types/lint/format remain the code verification basis.

The owner accepted Google's SDK licence. Official Google-signed portable ADB
connected after the Windows driver recovered and Chrome USB discovery was disabled;
the sequence does not prove a firmware/browser defect. The USB-only HTTPS sibling
localhost test required owner-accepted disposable leaf certificate warnings, not
phone CA installation or public DNS. The actual trusted public-domain path and
EC2 capacity still need deployment acceptance. Test services, owned phone test tab,
USB/browser forwarding, newly started ADB server and certificate key were cleaned
up and verified. Owner instructed to disable USB debugging; that setting remains
owner-controlled. No personal phone tabs/data, paid inference or AWS changes.

Local08 is now resolved. Local 02 account/network feasibility and parent CAP-04
remain open; 09 final architecture handoff still depends on02. Continue with
account/network evidence rather than provisioning or claiming cloud readiness.
Changes remain local, with no push; original checkout is preserved.

## Combined concurrency: automated slice verified — 2026-10-18

Local Ticket 08 remains **open for physical Android Chrome**. Automated changes
are on `codex/cap04-capacity`, based on `da59a56`. See
[capacity runbook](docs/cap04-capacity.md) and
[execution ledger](docs/superpowers/plans/2026-10-18-cap04-capacity.md).
Actual Caddy/built Storefront/Panel plus a single Agent worker pass independent
installed Chrome/Edge and mobile-emulated cohorts at 1/5/8 Shoppers. Five complete;
an eight-request held burst completes five and safely pauses three, with at most
two provider entries and three waiting. Cart isolation, foreign-session denial,
refresh without duplicate POST, fresh-cookie exhaustion and disabled inference
pass. Native service-tree CPU/RSS and exact queue timing are recorded separately
from preparation, intentional provider delay and browser completion. These are
Windows fixture/workstation measurements, not EC2 or live-model latency evidence.

Focused checks: 28 passed in 12.49s. Final serial full verification: **716
Python/browser tests passed in 733.52s**, exit 0, with two upstream WebSocket
deprecation warnings. **199 TypeScript tests**, builds/type checks, ESLint and
Ruff check/format pass. Durable ignored full log and exit-code JSON are under
`outputs/cap04-capacity-verification/`. Both independent reviews clear the
implementation and follow-up runbook/diagnostic corrections. Reports omit raw
conversations, codes and headers; test provider calls and sampling are bounded.

A combined real-Agent HTTP/lifecycle test covers five accepted model requests,
queued work, pending Actions, drain/activity arbitration and retained external
authority. It uses fake host/Storefront services; actual process restart/no-replay
browser evidence remains in the release/lifecycle regressions. Physical Android
is not inferred from emulation: the owner connected a CMF Phone 1 and enabled USB
debugging; Chrome discovery currently awaits device authentication. No phone
trust-store, public DNS or cloud changes have been made. Parent CAP-04 and Ticket
02 remain open; no paid inference or push. Original checkout remains untouched.

## Invitation-gated lifecycle rehearsal — 2026-10-18

Local Ticket 07 is resolved on `codex/cap04-lifecycle` from `476cb30`.
See [lifecycle runbook](docs/cap04-lifecycle.md) and
[execution ledger](docs/superpowers/plans/2026-10-18-cap04-lifecycle.md).
Focused lifecycle/browser checks: **17 passed in 56.29s**. Standards and Spec
reviews are clear after reproduced race/failure fixes. TypeScript **199** tests,
builds/type checks, ESLint, Ruff check/format and Prettier pass. Final serial
verification: **713 Python/browser tests passed in 728.29s**, exit code 0.
Durable ignored evidence is under `outputs/cap04-lifecycle-verification/`.
The bounded waiting service, generation/drain arbitration, accepted-work leases
and manual prewarming are locally rehearsed with real built shopping processes
and external persistent coordination. New starts require invitation validation;
background traffic does not reset inactivity, failed shutdown is never reported
stopped, and expired worker authority cannot silently resume uncertain Actions.
The shared-filesystem lifecycle transport is explicitly local-only; real remote
control storage, Lambda, IAM and instance lifecycle still need cloud qualification.
No paid inference, AWS, DNS or trust-store changes. Original checkout untouched;
work is local, not pushed. Next is 08 combined concurrent readiness; Ticket 02
account/network feasibility and parent CAP-04 remain open.

## Built release and recovery — 2026-10-18

CAP-04 local ticket 06 is resolved locally on `codex/cap04-release`, based on
`b9248bb`. Final serial verification passes **696 Python/browser tests in 691.70s**,
**199 TypeScript tests**, builds/type checks, lint and formatting. The ignored
full-suite log and exit-code record are under `outputs/cap04-release-verification/`.
See [owner runbook](docs/cap04-release-recovery.md) and
[execution ledger](docs/superpowers/plans/2026-10-18-cap04-release-recovery.md).
Allowlisted builds emit Storefront JavaScript and include pinned offline Node
production dependencies, built Panel/Bridge and Agent/runtime tools. Exclusive
install and manifests refuse modified artifacts, executable caches and unsafe
links. Configuration, catalogue, allowance, admission and logs remain external.
Preflight verifies schema/integrity/identities, built origins and disk/write
headroom without provider calls. Online catalogue backup/restore preserves WAL
revision/content and refuses existing targets or inference/admission history.

Nine focused release checks pass in 149.60s. The built-browser journey loses a
Mutation result after application, restarts Agent without duplication, rejects
old results/Confirmation answers, and restarts Storefront to reject old Undo and
actually registered Confirmation authority. Rollback selection retains charged
uncertain reservations and exhausted invitation quotas. Production process
rehearsal excludes test routes. TypeScript 199 tests/builds/types/lint pass.
Independent Spec review has no material gaps; Standards found an ignored-bytecode
bypass, reproduced RED then fixed GREEN and cleared. Final regression includes
that additional test. Caddy adapts bounded external logs. Native disposable WSL
permission proof passes for a non-root service identity; no system user/service
was installed. Linux service-manager/EC2 and abrupt external Windows launcher
termination are not qualified by this workstation evidence.

No real codes, paid calls, AWS, DNS or trust-store changes. Local unpushed work;
original checkout remains untouched. Next is 07
invitation-gated startup/idle shutdown; 02 account/network feasibility and parent
CAP-04 remain open. Domain linkage occurs at separately authorized provisioning,
after the remaining readiness, cost and AWS-model gates.

## Invited admission implementation — 2026-10-16

CAP-04 local ticket 04 is resolved locally on `codex/cap04-admission`, based on
merged main `83fc92a`. Final serial verification: **686 Python/browser tests passed
in 549.35s**, **199 TypeScript tests passed**; builds/type checks, lint and formatting
pass. See the
[owner operating guide](docs/cap04-invited-access.md) and
[implementation plan](docs/superpowers/plans/2026-10-16-cap04-invited-admission.md).
Production requires initialized admission storage and explicit finite bounds;
unconfigured local development remains opt-in. Codes are hashed in durable storage,
grants retain existing Shopper ownership, and absolute windows/redemption/session
quotas survive reopen. Codes never enter URLs, browser persistence or model input.

Admission covers HTTP, event delivery and each model entry after asynchronous
queue/key checks. Stop has a reserved bounded lane while retaining CSRF and task
ownership. Panel code entry, denied/expired/busy feedback and explicit stream
recovery are implemented for desktop/mobile. No uncertain Action is automatically
replayed. No prompts, phrase matching or shopping interpretation changed.

Independent Spec/Standards reviews found and cleared post-await revocation and
SSE429 recovery defects. Full regression exposed a simultaneous-tab early-Snapshot
race, fixed with a deterministic ownership regression and cleared by both reviews.
A later run passed 684 tests but hit a five-second initial code-form wait with an
empty UI shell; only that startup assertion now uses the existing 15-second
browser allowance. The final serial full result above supersedes earlier failures.

The serial run subsequently passed 665 tests before an older mobile evaluation
helper raced initial iframe navigation. The helper now awaits Panel readiness
and fixed-destination Frame navigation. A real-Panel delayed-start regression
fails against the old helper and passes with the fix; both reviewers cleared it.
The final full run includes that new regression and passes all 686 tests.

No real participants/codes, paid calls, trust-store, public DNS or AWS changes.
Ignored provider configuration/cap remains unchanged. Work is local, not pushed;
the original checkout's unrelated dirty documents are preserved. Next prefer 06
release/restart rehearsal; 02 account/network feasibility remains open, 07 depends
on 06, and parent CAP-04 remains open.

## Publication after owner smoke test — 2026-10-15

The owner tested the running Gemini3.5 checkout, accepted the result and explicitly
authorized push and merge. Delivery is tracked in
[PR #2](https://github.com/Homd11/shopping-copilot/pull/2), from
`codex/cap04-design` into `main`; consult that PR for current integration/CI state.
The seven outgoing implementation commits through `39f03ef` passed a full-history
scan for known credentials and credential-shaped data. Keys, reports and local
ledgers remain ignored. Services continue from the managed worktree. The original
`D:/agent depi` checkout has unrelated uncommitted documents and was preserved;
its local main/configuration are not synchronized by the remote merge.
The qualification results and next frontier02/04/06 below remain unchanged.

## Qualified replacement and durable allowance completed — 2026-10-15

OpenRouter `google/gemini-3.5-flash-lite` replaces the retiring 2.5 route in the
ignored configuration of this managed worktree. The separate original checkout
has older code and unrelated uncommitted documents; its configuration is unchanged.
Run the qualified implementation from this worktree until integration preserves
those documents. See [replacement evidence](docs/research/2026-10-15-gemini-replacement.md).
The accepted `intent-v32` cohort passes 43/44 core scenarios, all 19 safety cases,
all 9 filters and all 7 advice cases. Median model latency is 2.007s, p95 4.108s.
One relative cart increase incorrectly chose add and asked for variant details;
it remains a recorded task failure. Earlier failed cohorts are retained.

The final additional set used 72 POSTs/$0.09501011 within its approved $0.12.
The total key limit remains $2, reset Never; a final read reports usage 1.415450882
and remaining 0.584549118. No more paid calls were made after that verification.
Candidate reasoning uses minimal effort. General prompt/schema descriptions
separate literal name search from canonical type filters; read-only advice no
longer limits owned outfits/soft colours to store vocabulary. No runtime phrase
rules, query rewriting or safety-authority changes were added.

CAP-04 local ticket 05 is resolved: [owner instructions and acceptance](docs/cap04-inference-allowance.md).
An explicitly initialized SQLite ledger atomically reserves before shared model
entry, reconciles verified native costs once, retains uncertain charges, and never
recreates missing initialized storage. Persistent disable, finite queue/concurrency,
crash/reopen, duplicate, missing/corrupt/read-only/full storage and actual
interpretation/advice/repair paths are covered. Production real providers require
this configuration. Paid server speech is disabled when guarded until audio has
equivalent accounting; typing/browser speech remain available. No deployment
ledger, AWS resource or public DNS was created.

Verification: **665 Python tests passed in 501.35s**, **198 TypeScript tests passed**,
build/type checks, lint and full formatting passed. Independent Standards/Spec
reviews cleared the main runtime and prompt changes after regressions fixed their
findings. Reviewers hit their usage limit on the final small qualification
claim/continuation delta; it was self-reviewed and regression-tested, not independently
cleared. Qualification runtime source hashes match the accepted run.

Current frontier: 02 account/network feasibility, 04 invited admission, 06 release and
restart rehearsal. Prefer 04 next; 06 is now unblocked by 03/05. CAP-04 remains open;
Bedrock pricing/access and cloud acceptance remain later gates. Changes are local,
not pushed. Keep keys, local ledgers, raw reports and scratch tracker ignored.

## CAP-04 production origin journey completed — 2026-10-14

Ticket 03 is resolved for local production-style configuration. See the
[implementation evidence](docs/research/2026-10-14-cap04-production-origins.md) and
[operating instructions](deploy/README.md). Panel builds use validated public
origins; Storefront HTML supplies validated origin metadata to Bridge. Caddy serves
built assets and proxies fixed loopback services without asset rewriting. Public
private/test routes are blocked; production requires explicit service secrets and
disables evaluation endpoints. Existing Strict host-only cookies, journal,
Confirmation, Undo and uncertain-action recovery remain in place. SSE now supplies
idle keepalive comments without advancing cursors or touching activity.

Installed Chrome 155.0.8059.40 and Edge 155.0.4283.45 passed the configured sibling
HTTPS journey with independently verified third-party blocking. Browser reads
confirm initial/periodic heartbeat delivery after Caddy; native cursor reconnect
following a completed cart Mutation produces no duplicate cart POST/revision.
Stop preserves the cart while cancelling pending Confirmation. Unknown Host and
public private/test paths are rejected; personal HTML/cart responses are no-store.
Temporary test CAs and keys were removed and independently checked.

Verification: **627 Python tests passed in 474.65s**, **198 TypeScript tests passed**,
builds/typechecks and repository lint/format passed. Both independent reviews were
completed; the Spec review's three material findings were reproduced and fixed
with focused regression/browser evidence. No unresolved findings are recorded.
No prompts, paid calls, provider caps, public DNS or AWS resources changed.
Work is committed locally on `codex/cap04-design`, not pushed.

Current frontier: 02 account/network cost feasibility, 04 invited admission and
05 durable inference allowance. Prefer 05 next for bounded independent local work;
04 remains available. AWS ingress selection, current account/credit evidence,
Android hardware, release/restart, lifecycle, capacity and deployed acceptance are
still open. Parent CAP-04 remains open and unchanged. Do not deploy the evaluation
fault-injection servers or treat the supplied-certificate Caddy rehearsal as
public certificate issuance.

## CAP-04 domain decision and passing sibling-hostname proof — 2026-10-14

The owner purchased `scpilot.tech` through .tech Domains and approved
`app.scpilot.tech` (Panel/Agent) and `store.scpilot.tech` (Storefront). This replaces
the no-domain constraint only; AWS remains Free-plan/credit-only. The earlier
first-party journal proposal is superseded before implementation. Existing
production cookies, Bridge journal and recovery are unchanged.

[Browser comparison](docs/research/2026-10-14-cap04-sibling-hostnames.md): installed
Chrome 155.0.8059.40 and Edge 155.0.4283.45 pass the sibling HTTPS layout with
verified third-party blocking using an independent unrelated iframe. Storefront
sessionStorage is available, DOM origins remain isolated, and original host-only
Strict/Secure/HttpOnly cookies work. The journey covers separate carts, product/add,
refresh, second-tab ownership requirement, Confirmation, Undo and a real SSE
reconnect after an Agent cart Mutation. The native Last-Event-ID is checked;
cart POST count/revision remain unchanged. It does not qualify every in-flight
recovery case or a completed tab takeover. Temporary CAs/private keys were removed.

Ticket 01 resolves desktop layout feasibility under this approved amendment;
03 is unblocked. Current frontier: 02 account/network costing, 03 production origin
configuration, 05 durable inference allowance. Next implement 03: replace probe
asset rewriting with actual configured origins and a production-style proxy.
The [DNS/HTTPS plan](docs/cap04-domain-https-plan.md) specifies the chosen public
names and conditional certificate/DNS sequence. Public NS delegation was read;
no DNS edits, AWS APIs/resources, paid inference or push occurred. Android hardware,
account entitlement, actual public TLS, all-in cost and deployed acceptance remain
open. Parent CAP-04 remains open and unchanged.

Verification: both installed-browser runs, 182 TypeScript tests, two cleanup
regressions, builds/typechecks and repository format/lint passed. Both independent
reviews have no remaining findings after synchronizing the frontier. The full
Python application suite was not repeated for this probe/documentation-only change;
its prior result remains historical evidence. Work is committed locally, not pushed.

## CAP-04 browser feasibility: negative result — 2026-10-13

Ticket 01's disposable HTTPS experiment found a blocker; see the
[browser report](docs/research/2026-10-13-cap04-browser-proof.md) and
[reproducible probe](eval/probes/README.md). Installed Chrome 154.0.8037.98 and
Edge 155.0.4283.45 reject Strict and unpartitioned Storefront cookies under verified
third-party blocking. Partitioned cookies restore cart HTTP access, but iframe
`sessionStorage` throws SecurityError, stopping Bridge initialization. Earlier
CDP-only Chromium journey success is preliminary and does not qualify this topology.

Ticket 01 is needs-triage with an explicit negative outcome; ticket 03 remains
blocked on a successful supported-browser proof. Next design work must preserve
the Action journal and navigation recovery without assuming iframe sessionStorage,
or revise the serving topology. Do not insert a memory-only fallback, adopt the
proxy as production infrastructure, or ask Shoppers to disable privacy. Independent
02 (account/network feasibility) and 05 (durable allowance) remain available.

No production sources, AWS resources or paid model calls changed. Temporary
name-constrained user-store CAs were explicitly approved, installed for each run,
removed by exact thumbprint and checked absent; generated private keys were removed.
Verification: 619 existing Python regressions passed in 512 seconds; the two new
cleanup failure tests passed separately after their red/green fix. All 182
TypeScript tests, workspace builds, repository formatting and lint passed. Both
independent review findings are resolved. This verifies the unchanged local
application and probe safeguards, not the failed cloud topology. Parent CAP-04 stays open.

## CAP-04 specification and tickets published — 2026-10-11

The owner confirmed the design and availability decisions after review. The
[specification](docs/cap04-spec.md) and [nine-ticket breakdown](docs/cap04-ticket-breakdown.md)
are finalized. The ignored local tracker contains the ready-for-agent specification
and nine individual tickets under `.scratch/cap04-cloud-readiness/` in this worktree.
Initial frontier: 01 (cross-site HTTPS browser proof), 02 (account/network costing),
and 05 (durable inference allowance); begin with 01.

Approved: desktop Chrome/Edge and Android Chrome, five simultaneous Shoppers as a
test target, one revocable invitation per tester/testing window, and shutdown after
60 minutes of genuine inactivity. Lambda wake is conditional on eligibility and
complete costing; wake requires an invitation and manual start remains the fallback.
Tests must protect active work through drain/stop races and preserve invitation
expiry, allowance accounting and uncertain Action outcomes across restart.
CAP-04 remains open; its parent ticket is unchanged. This publication changes no
runtime code and creates no AWS resources or additional spending authorization.

## CAP-04 design revision — 2026-10-11

The owner approved retaining one EC2 host and SQLite while resolving public HTTPS,
persistence and spending controls before deployment. The [revised design](docs/superpowers/specs/2026-10-11-cap04-cloud-readiness-design.md) supersedes old single-shopper assumptions; it preserves the implemented asymmetric Agent/Storefront restart behavior.
Two generated CloudFront HTTPS origins with a VPC origin remain a candidate, not a
selected or provisioned topology. Cross-site iframe identity, Free-plan entitlement,
complete egress and pricing remain unresolved. Catalogue storage is distinct from
ephemeral carts/tasks and the proposed durable spending ledger. Next: review the
published ticket 01 and run its disposable local browser identity rehearsal.
CAP-04 remains open. No AWS account access, resources, paid calls or runtime changes.

GitHub PR #1 merged as `0a7836d` after both CI runs passed. The preceding CI fixes
added missing evaluation dependencies and clean-checkout health-check prerequisites.

## CAP-02 / CAP-03 closed under approved synthetic scope — 2026-10-09

The owner approved replacing independent-human evaluation with a clearly disclosed
synthetic benchmark and at most $0.20 of API usage inside the existing $2 key cap.
[Closeout](docs/cap02-cap03-closeout.md) and the
[executed notebook](notebooks/cap03-synthetic-holdout.ipynb) record completion.
The 120 new messages cover ten intents/four languages, three per cell. Existing
210 training / 53 validation and seven selected artifacts are unchanged. Protocol
commit `f2695b1` precedes authoring; reviewed dataset/runner commit `7e20365` precedes
predictions. The coordinator AI reviewed all drafts after an additional reviewer
hit usage limits; no human review is claimed. Shared scenario semantics and explicit
disambiguators limit independence and realism.

All eight contenders completed 120 predictions: Gemini 120 correct, Complement
Naive Bayes 74, Logistic Regression 69, Linear SVM 63, embedding LR 59, embedding
MLP 55, Random Forest 46, XGBoost 40. This is intent-only synthetic classification,
not a whole-agent accuracy/safety score. Paid usage was $0.0148178, all known,
120 attempts and zero repairs/failures. Embedding startup failures were retained;
a cache-only recovery made their first predictions, retaining five other results.
No refitting, prompt retuning or label changes after predictions.

567 non-browser Python tests passed; four recovery tests additionally passed.
Notebook execution, release/artifact checks and formatting/lint checks pass.
Current runtime and running services are unchanged. Independent real-shopper
validation is a disclosed future limitation outside the amended ticket closure.
Next: CAP-04 credit-only architecture/public HTTPS/abuse controls, then CAP-05
model qualification; no provisioning, push, deposit or cap increase occurred.

## Recommendation-to-cart boundary and latency repair — 2026-10-08

The reported “first football shoe, blue, size 43, add it” failure was reproduced
with captured provider output. Two application defects were involved: the model
could select the known product but `cart_edit` prohibited its identity, and the
flat generation schema invited discovery fields that runtime cart validation
rejected. Earlier probes on an already-open product page did not cover this
navigation-to-add transition.

The established path now retains the model-selected, observed product identity
for add only. Runtime opens that product, checks the returned origin and product
path, binds the sole enabled visible add form, validates requested variants and
executes the existing cart sequence. Unknown products, ambiguous/disabled forms,
truncated snapshots, wrong pages and intervening page changes cannot authorize
the add. Existing cart-line edits still require observed line controls. Duplicate
results and uncertain mutation recovery retain their existing safeguards.

`intent-v31` uses operation-specific generation schemas derived from persisted
field types; cart/navigation decisions no longer expose discovery metadata.
Runtime still validates `StructuredIntent`, quantities, capabilities and authority.
Repair diagnostics use that persisted schema. OpenRouter's schema adapter converts
string `const` restrictions to equivalent string `enum` restrictions after a live
response invented an unsupported action name. Numeric enums caused empty decisions
on the pinned Gemini route: an isolated probe removing only the numeric enum
succeeded, while adding an object type to the union did not. Numeric literal
restrictions therefore remain local; existing live version-8/9 compatibility is
preserved and versions outside that policy are rejected. No transport wrapper is
needed. No language phrase rules, output
alias rewriting, or automatic variant substitution were added.

Latency changes: OpenRouter prioritizes latency within the unchanged model and
price ceilings; private Storefront requests reuse an HTTP connection pool. Every
shopper authorization check still sends a fresh validation request, with revocation
and distinct-shopper coverage. Constructing a new HTTP client had cost roughly
160–250 ms per check before a 5–40 ms local request. The pool closes at app shutdown.

Live evidence so far includes a full HTTP/SSE recommendation/advice/add sequence
and successful actual Panel/Bridge/Storefront cart mutations in separate browser
contexts. The exact selected cart line was `shoe-12`, blue, size 43, quantity 1;
a second shopper's cart stayed empty. After pooling, full browser recommendation
took about 7 seconds and add 5.9 seconds; another add needed a model repair and
took about 9.6 seconds before the singleton-enum adjustment. These are exposed
regression observations, not an unseen accuracy score or latency guarantee.

Final verification on 2026-10-09 (local time): the actual browser reproduction
passed with recommendations in 6.954 seconds and add in 5.375 seconds, including
navigation and fresh variant selection. Three model calls, no repair calls, exact
`shoe-12` / blue / 43 / quantity 1 cart line, and an independent shopper remained
empty. This is a measured regression result, not a latency or universal-success
guarantee. Normal services were restored after the bounded diagnostic runtime.

Verification includes an earlier full Python run (583 passed), followed after the
provider compatibility correction by 536 non-browser tests and focused tests for
the retained live-version policy (11 focused schema checks). All 182 TypeScript
tests, builds, ESLint, Ruff, Prettier and diff-whitespace checks passed. No
application safety checks were weakened to accept
an invalid model decision. Two independent reviewers examined execution/schema
changes; their repair-feedback finding was fixed. Final review also corrected a
test/report mismatch: version 8 remains accepted by the existing live compatibility
policy, despite the generation schema requesting version 9. The regression now
checks the actual live validator. Raw traces and browser timing artifacts remain
ignored under `work/manual-test/`.
The key's total non-resetting cap remains $2; latest metadata reports about
$1.089 used in total (provider accounting may lag). SQLite and shopper isolation remain active; experimental
retrieval stays disabled. No AWS resources, push or cap increase.

## Short conversational answers: role-aware context verified — 2026-10-08

The owner requested fixing the known styling failure before handing testing back.
The restored path remains active; experimental retrieval stays disabled. Interpreter
prompt `intent-v29` now receives bounded previous turns as actual shopper/assistant
messages rather than embedding them in system metadata. Only the newest shopper
message is the request to execute. System/tool roles from history are excluded.
The latest Copilot reply is retained up to the advice contract's 2,400-character
bound, preserving a question after a long comparison; older entries remain capped
at 500 characters and history remains limited to 12 entries.

The prompt explicitly distinguishes an answer about an owned item from constraints
on a desired product. The model continues to perform that interpretation. No phrase,
colour-word or category-matching logic was added. Schema/prompt descriptions also
tell the model to retain an identifiable desired category for catalogue-backed
advice, avoiding empty product evidence when a requested type is known. Action,
confirmation, snapshot and ownership validators are unchanged.

Verification:

- 520 non-browser Python tests pass; Ruff lint and format checks pass. Regression
  coverage verifies question retention, role routing, bounded history, and existing
  cross-session/origin isolation. Browser checks were not run against the owner's
  occupied manual-service ports. Independent reviewer completion remains unavailable
  after the earlier reviewer usage-limit failures; the change received local review.
- A real HTTP/SSE two-turn run correctly attached the short colour answer to shoes
  and continued advice. That run exposed an omitted desired category; the subsequent
  contract-description correction was then verified separately through the real
  interpreter, SQLite compatibility reader and advisor.
- Four exposed live semantic cases passed: Arabic shoe-colour answer, Franco-Arabic
  `aswd kda`, explicit desired green shirt, and correcting the shoes to blue while
  requesting a white shirt. In the original case, desired shirt colour remained null,
  shoes became black, and fresh cards plus Arabic advice included blue/white options.
- The observed product-page add request still produced the correct cart-edit intent,
  using one format repair in its live probe. No real cart mutation was performed by
  these probes. These bounded cases are regression evidence, not unseen accuracy.

Raw traces remain ignored at `work/manual-test/live-conversation-v29.json`,
`work/manual-test/live-conversation-v29-flow.json`, and
`work/manual-test/live-answer-semantics-v29.json`. Together they report approximately
$0.0143 in provider usage under the unchanged $2 total, non-resetting cap.
Latency remains variable: some interpretation calls took about 2.4–3.9 seconds,
another 16.6 seconds, and one 47.3 seconds. This fixes the reproduced interpretation
failure; it does not establish a response-time guarantee or solve provider latency.
SQLite and shopper isolation are retained. No push, AWS deployment or budget increase.

## Established conversation path restored; styling interpretation still open — 2026-10-08

At the owner's request, experimental catalogue retrieval is disabled again:
`CATALOGUE_RETRIEVAL_ENABLED=0` in the private local configuration and both ignored
manual-service launchers. Only the Agent was restarted. SQLite, the Storefront
process, shopper isolation and existing carts were retained. Agent health and both
UI roots return HTTP 200. Refresh the Panel for a fresh Agent session.
Repository defaults already disable retrieval; experimental code is retained but
inactive. No combined-response/routing optimization was ported into the restored
path, and no prompt, language rule or safety guard changed during this rollback.

The established `interpret_message` / catalogue-reader / standalone-advisor path
is active. Its catalogue compatibility endpoint reads the SQLite repository.
All 449 Agent tests pass. Browser/full-workspace checks were not rerun for this
configuration rollback; the manual Storefront was left running to retain carts.

Bounded live baseline with the existing $2 total non-resetting cap:

- Styling request through the HTTP/SSE application seam returned advice and cards
  in two model calls, about 11.0s overall in this run.
- A subsequent bare "black" completed in one call, about 2.8s, but was wrongly
  applied to the desired shirt colour. A separate reconstruction including the
  explicit question about the shoes' colour also produced that wrong assignment.
  **This semantic bug remains open in the restored interpreter.** Rollback is not
  evidence that all prior behaviour or this exact conversation now works.
- The green, size-43 add request on a supplied product-page snapshot produced a
  valid cart-edit intent with the observed button ID, quantity one, in one 3.485s
  call. This is interpretation evidence, not a browser cart mutation or a complete
  recommendation-to-add journey.

Five model requests reported $0.0057311 combined cost. Single-run timings are not
latency guarantees. The live probes used isolated test sessions/snapshots and did
not alter the owner's cart. Ignored traces are
`work/manual-test/live-stable-rollback.json` and
`work/manual-test/live-stable-targets.json`.

Next: address the general distinction between an answer about an owned item and
a requirement for a desired product, using conversation-level evidence without
phrase matching. Keep experimental retrieval disabled while doing that work;
optimize the established flow only against measured, complete conversations.
No push, AWS deployment or additional budget increase occurred.

## Retrieval latency: fewer calls and bounded live timings — 2026-10-08

The owner reported roughly 20-second replies and a stopped product-opening request.
Read-only provider metadata confirmed $0.987338002 used under the unchanged $1
non-resetting cap, leaving $0.012661998. The preflight reservation can block a request
before that balance reaches zero. This allowance problem is separate from latency.
The owner subsequently raised the key cap to $2 total. Read-only metadata confirmed
limit=2, reset=null and $1.012661998 remaining before verification. The application
now permits an explicitly configured cap up to $2; its default remains $0.25. The
private local configuration was updated to match. No top-up or guard bypass occurred.

The previous recorded successful search spent 10.063s, 1.719s and 2.358s in three
sequential model requests. The approved optimization combines read-only product
selection and grounded advice in `catalogue-decision-v7`, reducing the normal
search/advice path from three model calls to two. Existing known-product context
starts follow-ups in the established intent interpreter, reducing product opening
from two calls to one. The model still decides meaning: a changed goal routes back
to fresh retrieval within the same three-decision budget. No phrase rules were added.

Combined advice receives the shared grounding policy and complete bounded product
facts with deterministic eligibility labels. Final details refresh compares product
facts, revision and requirement statuses against the evidence used for the response.
This refresh includes unselected candidates that may be mentioned in comparisons,
in batches of at most nine. Any change discards that prose and requests a rewrite
within the original budget. If the full evidence pool cannot be refreshed within
the read budget, discard combined prose and use the existing standalone advisor
with only freshly checked selected products.
Legacy responses lacking combined prose retain the standalone advisor fallback.
No action/confirmation authority is granted by advice, and current action validators,
ownership checks and cancellation checks remain in place.

Verification: 516 non-browser Python tests pass, plus two subsequently added
focused large-pool regressions (518 distinct passes). Checks include preparation and HTTP/SSE call-count
checks, changed-fact rejection, unknown-ID rejection, goal changes and the real
OpenRouter adapter with mocked HTTP and unchanged budget bounds. A full Python run
had 514 passes, but 31 failures and 17 setup errors because browser evaluation ports
were occupied by the owner's manual services. That run is not a full-suite pass;
the services were retained to preserve the owner's cart. The browser fixture was
updated for the new protocol. Ruff lint/format checks pass.

One bounded live search returned three products and Arabic advice in two model calls
(2.219s + 3.313s = 5.532s in provider requests), versus 14.140s across three calls
in the prior recorded trace. A follow-up asking to open the Keeper product resolved
the correct product ID in one 2.155s intent call. These are single-run preparation
measurements, not browser end-to-end latency or a distribution. The subsequent
all-discussed-products refresh correction passed offline regression checks without
another paid call. The three live requests reported $0.0036626 combined cost.
Ignored traces: `work/manual-test/live-latency-v7.json` and
`work/manual-test/live-latency-open-v7.json`. Broader language and live browser
qualification remain open; no universal speed or correctness claim is made.

Independent review started on both axes but hit reviewer usage limits. Before that,
the specification reviewer identified missing added-date and garment-position facts
in the shortened evidence projection; both were restored with a regression check.
Final review completion remains unavailable. Local changes are not pushed or deployed.
The local Agent was restarted with retrieval enabled and the matching $2 cap;
Agent health and both UI roots return HTTP 200. Refresh the Panel for a new session.
The Storefront and Panel processes were retained, preserving existing carts.

## Retrieval repair: targeted live recommendation and routing checks pass — 2026-10-08

This entry supersedes the failed verification and runtime rollback below. The owner
authorized continued repair within the existing $1 total, non-resetting OpenRouter
key cap. No cap increase, top-up, deployment or push was performed.

Captured responses exposed repeated empty nested action intents in the retrieval
response. The model-facing retrieval contract now separates read-only recommendations
from an `execute` routing decision. Execution routes the original shopper message,
context and snapshot through the established action interpreter and validators;
routing annotations confer no action authority. Routing and interpretation share
the existing three-decision budget, cancellation checks and single provider attempt.
Legacy nested finish responses remain supported internally, but are not requested
from the provider. No phrase matching or language dictionaries were introduced.

Read decisions can carry subjective preferences separately from factual requirements.
The advice prompt asks for a provisional, grounded styling comparison before an
optional follow-up question. Existing fact, target, quantity, confirmation and
mutation guards remain in force. Models can still classify taste imperfectly;
this change does not claim universal semantic accuracy.

Final live evidence using `catalogue-decision-v6` and `advice-v4`:

- The original Egyptian Arabic football-shoe request (size 43, distinctive style)
  returned three catalogue products and an Arabic comparison grounded in their
  colours, followed by an optional preference question, with no failure events.
- The cart-navigation request produced a valid navigation intent through the
  established interpreter, using two model calls and no catalogue reads. This
  verifies the preparation seam, not a browser click or a cart mutation.
- All 434 Agent tests pass, with Ruff checks passing. Independent specification
  review found no outstanding safety issue; the separate standards reviewer was
  unavailable because of its usage limit. Browser/full-workspace checks were not
  repeated for this Agent-only change. Broader live qualification remains open.

Raw traces remain ignored under `work/manual-test/live-final-v6.json` and
`work/manual-test/live-navigation-routed.json`. The latest read-only key metadata
reports $0.973327902 used and approximately $0.02667 remaining. Reported usage rose
by about $0.01947 during this repair; these are provider-reported snapshots, not a
separate billing reconciliation. No further paid probes are needed for this fix.

The local manual-test Agent was restarted with retrieval enabled and lexical
ranking; Agent health and both UI roots return HTTP 200. Repository defaults remain
opt-in. SQLite and shopper isolation remain
active; the Storefront process and existing carts are retained. Refresh the Panel
after the restart to establish a fresh Agent session.

## Final bounded verification: technical errors cleared, recommendation gate failed — 2026-10-08

The owner authorized one final set of at most four model requests / $0.08 reserved
within the unchanged $1 total cap. The current `catalogue-decision-v2` flow completed
in two requests, reporting $0.0014316 combined, with no provider or response-validation
errors. The model searched `football shoes`, retained size 43 and received catalogue
results. It nevertheless classified the vague style preferences as unverified
requirements and ended with an Arabic clarification about their meaning, with zero
recommendation cards. No advice completion was requested. This does not pass the
intended recommendation/advice acceptance case; successful JSON is not UX success.

No additional calls were made after this result. Diagnostics remain ignored at
`work/manual-test/live-final-verification.json`. The previous chat flow remains active
with retrieval disabled; SQLite and shopper isolation are unchanged. Next work must
address how retrieval carries subjective preferences into recommendations, without
phrase rules or weaker factual/action validation. Do not reactivate the new path on
the basis of this check. No runtime code changed during this verification turn;
the preceding 430-test evidence remains the last automated run.

## Retrieval repair: first-read constraint preservation — 2026-10-08

A further owner-approved four-request diagnostic set exposed the first-read
duplicate-field rejection: the model supplied size as a predicate without repeating
it in requirements. Rejecting this read consumed repair attempts and allowed a later
read to establish a different original-requirement set. The coordinator now freezes
the union of both model-supplied lists, deduplicates equal predicates and retains
normal schema/bounds checks. Regression tests verify refinements and final refresh
cannot lose that initial condition, and explicit exclusions are preserved.

The retrieval prompt restores the established subjective-preference guidance,
describes English indexed attribute terms so the model can translate descriptive
queries, and requests shopper-language questions. No phrase dictionaries were added.
The four diagnostic requests reported $0.0025549 combined. They did not establish a
complete recommendation/advice success: v1 clarified taste after an empty lexical
search; intermediate v2 encountered the duplicate-field problem. Raw responses and
validation diagnostics were retained only under ignored `work/manual-test/`.

All 430 Agent tests and Ruff checks pass; both independent review axes found no
outstanding issues. Browser/full-workspace tests were not repeated. The previous
chat path remains active until the repaired retrieval path passes live verification.

## Live retrieval qualification failed; manual runtime rolled back — 2026-10-08

The owner's next manual request exposed a separate provider HTTP 400. One
authorized diagnostic request reproduced `reference to undefined schema at oneOf.0`.
The subsequent authorized verification was capped at three requests / $0.06
reserved, within the unchanged $1 non-resetting key allowance. Reference expansion
first exposed Gemini's `too many states for serving` rejection. The OpenRouter
adapter now expands references and sends structural constraints, with all original
value/resource bounds still enforced by the unchanged local response validators.
Its traversal preserves property names and literal metadata.

The remaining two requests accepted this schema: one produced a valid search for
football shoes, size 43, with distinctive/eye-catching preferences; the next failed
local validation. The exact second-output validation details were not retained.
The two completions reported a combined $0.0014136; rejected requests returned no
usage. No full search/advice success is claimed. The four authorized requests were
used; further live verification requires approval. All 428 Agent tests pass, plus
Ruff and focused schema/provider regressions; browser/full-workspace tests were
not repeated. Offline passes do not close live qualification.

The current local Agent was restarted with `CATALOGUE_RETRIEVAL_ENABLED=0` to restore
the previous chat path. SQLite, shopper isolation and the running Storefront remain
active. The new retrieval flow stays opt-in and unqualified; investigate the exact
remaining response-validation failure before activating it again. No deployment,
push, key-limit increase or phrase matching was introduced.

## Manual retrieval test: provider-boundary correction — 2026-10-08

Manual testing exposed a startup-blocking integration error: retrieval requested
2,200 output tokens while OpenRouter permits at most 2,048 under the existing
application budget guard. The coordinator then misclassified the budget rejection
as invalid model output and exhausted its attempts before asking a misleading
clarification. Retrieval now requests 2,048 tokens and only retries malformed
provider output; operational failures propagate to the existing error handling.
All 421 Agent tests pass, including actual OpenRouter adapter tests with mocked
HTTP for valid/malformed responses and budget/configuration propagation. Ruff
checks pass. Browser/full-workspace tests were not repeated for this Agent-only
correction. No paid verification calls, spending-limit changes or language rules
were added. Live semantic qualification remains open; local manual testing uses
the opt-in retrieval path with lexical ranking.

## Catalogue retrieval implemented locally; activation pending — 2026-10-08

The approved SQLite repository, private bounded search/details service and opt-in
model-directed retrieval/advice flow are implemented on `codex/shopper-isolation`.
Shopper isolation and Action/Confirmation boundaries are preserved. The combined
browser scenario passes through real database reads, advice, open/add/multi-line
quantity changes and two independent shopper contexts. Verification covers 534
distinct Python tests (531 in a clean full run plus three focused additions) and
182 TypeScript tests across full/focused runs, with format/lint/build checks green.

[Verification and qualification](docs/catalogue-retrieval-verification.md) records
checks, review fixes and the exposed offline comparison. Lexical/hybrid overall
target recall@10 is 67.5%/85%, but raw Egyptian Arabic remains 0%/40%. The new
path stays opt-in (`CATALOGUE_RETRIEVAL_ENABLED=0` by default) pending separately
budgeted actual-model evaluation and host measurements. SQLite is active; the
legacy advice path reads the same database through its compatibility endpoint.
No paid calls, budget increases, AWS resources, push or deployment occurred.
Original dirty checkout and frozen CAP-02/03 datasets/results remain unchanged.
The old catalogue source is archived by its existing hash for baseline loading.

## Shopper isolation implemented locally — 2026-10-08

The approved pre-deployment isolation slice is implemented in the separate
`codex/shopper-isolation` worktree. Each browser profile owns its cart, revision,
Undo, confirmations, fictional login/orders and Agent sessions; same-profile tabs
share commerce and retain explicit task takeover. Private challenge-bound linking,
cookie/CSRF authorization, bounded registries and per-event/model-admission checks
prevent foreign-session access and stale ownership. Restart, expiry and identity
changes require safe recovery without replaying uncertain Actions.

[Verification and operational limits](docs/shopper-isolation-verification.md) record
passing evidence for all **511 distinct Python tests** across full/focused runs and
**169 TypeScript tests**, plus builds/typechecks, lint/format and credential/artifact
checks. This is not an uninterrupted green full Python run: a login fixture and SSE
reconnect/teardown issues were corrected and affected checks rerun. Both independent
reviews have no outstanding actionable findings. Temporary SSE interruptions retain
cursor-based reconnect; revoked/expired authority still closes delivery.

Normal local startup now requires `python scripts/init_local_identity.py` once to
create the ignored restricted service-identity file; scripted evaluation supplies
its own ephemeral secret. The initializer was not run against the owner's local
workspace. No provider calls, AWS resources, budget changes, push or deployment
occurred. Original dirty checkout changes are preserved; implementation is not merged
there. Public HTTPS/cookie topology, global inference allowances, abuse controls and
Bedrock qualification remain CAP-04/05/06 gates. CAP-02/03 independent evaluation is
unchanged and remains open.

## CAP-04 credit-only planning — 2026-10-07

The owner requires zero out-of-pocket spending, a domain-free public link for independent testers and approximately two months of hosting. They created a personal AWS account during planning; their screenshot shows Free account plan, $100 remaining and plan end 7 April 2027. This is screenshot evidence, not an account/service-access audit. The additional advertised $100 is conditional, not a current balance.

[Current constraints](docs/cap04-credit-only-plan.md) supersede the older supervised/domain assumptions. [Official-source research](docs/cap04-pricing-research.md) gives a us-east-1 reference: $40.35 for 60 days of t3.small, 20 GB gp3 and one public IPv4; roughly $44.31–$50.24 including 10,000 assumed model calls plus 300 qualification calls for one candidate. Public HTTPS, transfer/logging and other costs remain excluded; no complete quote or spending authorization is claimed. Stay on Free plan; no upgrade or resource creation is authorized. Resolve shopper/cart isolation, domain-free HTTPS, abuse limits, model eligibility and full cost locally before provisioning. CAP-04 remains open.

The CAP-01 execution register now links the prepared PDFs/infographic and seven-family exploratory results. Existing PDF/source hashes remain unchanged; owner/lecturer review and official submission are pending. Verification: estimate arithmetic, local links, seven PDF/source hashes and repository formatting passed. Separate Spec and Standards reviews found no outstanding issues after updating account status. Documentation only; runtime tests were not repeated. No AWS API access, provider calls, resources, secrets, budget changes or push occurred. Unrelated local changes are preserved.

## Executed CAP-03 Jupyter notebook — 2026-10-07

The owner requested a notebook presentation of the seven-family results. [The executed notebook](notebooks/cap03-model-comparison.ipynb) contains 18 cells, including nine successfully executed code cells: source/release integrity checks, independent metric recomputation, model and language tables, saved charts, selectable full error analysis, all 46 trials, timings, provenance and optional reproduction instructions. [Opening instructions](notebooks/README.md) cover VS Code/JupyterLab.

Run All only reads local evidence. It does not retrain, download weights, load joblib artifacts, call providers or modify the Storefront. Saved outputs are included for notebook viewers. The same synthetic/exposed and reused-validation limits remain explicit. Notebook schema validation, clean-kernel execution, saved output checks, source integrity and repository formatting passed; application tests were not repeated for this presentation-only addition. Both reviews found no actionable findings. Original experiment reports, runtime source, provider settings and unrelated local edits remain unchanged. CAP-02/03 final evaluation remains open; no paid calls or push occurred.

## Seven-family offline comparison completed — 2026-10-07

The owner approved extending CAP-03’s exploratory comparison to five TF-IDF classifiers and two frozen-embedding heads, then authorized the local RTX 3060. The [pre-fit protocol](docs/cap03-model-comparison-protocol.md) fixed 46 candidates on the unchanged 210-training / 53-validation / zero-unseen release. All 46 converged. [Results](docs/cap03-model-comparison-results.md) retain all trials, errors, language metrics, predictions, matrices, timings, package/source hashes and local artifact bindings.

Frozen multilingual embeddings + Logistic Regression led at **23/53 correct (43.40%), macro-F1 0.4304**; embedding MLP 22/53, 0.4189; Complement Naive Bayes 21/53, 0.3987; TF-IDF Logistic Regression 20/53, 0.3776; Linear SVM 18/53, 0.3294; Random Forest 17/53, 0.3071; XGBoost 13/53, 0.2615. Small selected-on-validation differences are exploratory, not independent quality evidence. Overall classification remains weak. The encoder used CUDA 13.0 on the RTX 3060; classifier heads used CPU. No encoder fine-tuning, new phrase rules, runtime integration or paid inference occurred.

Verification: 14 focused experiment regressions passed. Full Python run: 485 passed and one browser page-creation infrastructure failure; the affected SPA test passed in isolation, giving passing evidence for all 486 distinct tests without claiming a clean uninterrupted run. All 155 TypeScript tests, builds/typechecks, ESLint, Ruff, formatting, both frozen-release checks and report/model/embedding hashes passed. Ordered cached feature IDs/shapes match the release. Spec review found a missing persisted embedding artifact; it was fixed before fitting and rechecked. Standards review found no actionable issue. Original data, both earlier pilots, application source and unrelated local changes are preserved.

The CUDA installer initially stalled at the mirror; the official primary-host download was resumed and verified against PyTorch’s published SHA-256 before installation. Evaluation-only dependencies and large artifacts remain outside runtime packaging; cached weights, local models, features and installer files are ignored. CAP-02 independent evaluation and CAP-03 final same-input LLM comparison remain open. No cloud resources, provider cap change or push occurred. The next evidence step needs an explicit independent evaluation arrangement rather than further tuning this reused validation set; CAP-04 design can proceed separately.

## Second synthetic pilot frozen and evaluated — 2026-10-07

The [expanded protocol](docs/cap03-expanded-pilot-protocol.md) and [results](docs/cap03-expanded-pilot-results.md) record a second development-only pilot: 308 synthetic/exposed drafts, 263 eligible and 45 excluded, frozen into **210 training / 53 validation / zero unseen**. Bounded legacy/context overlap review added four conservative links; 37 whole components remain, largest 137 original rows. All ten intents meet declared row, language and group support. The pre-fit policy explicitly accepts two training/one validation components per intent instead of the earlier four-family authoring target. Independent human gold and exhaustive private-history deduplication remain unavailable.

All twelve unchanged TF-IDF/Logistic Regression candidates converged. Selected character 3–5 grams, C=0.1, balanced weights: **20/53 correct (37.74%), ten-label macro-F1 0.3776**. Advice and guarded mutation each scored 0/4. This is validation-selected synthetic development evidence, not an unseen quality claim, controlled improvement over pilot 1 or LLM comparison. All trials, predictions and confusion matrices are published. The original pilot, runtime, prompts and phrase rules remain unchanged.

Verification: deterministic allocation reconstructed identically; both releases and all report/source bindings validate. Separate Spec and Standards reviews found no remaining actionable issues after fixing atomic publication; failed formatting/validation leaves no partial release. All 472 distinct Python tests have passing evidence across the combined/focused runs, alongside 155 TypeScript tests, builds/typechecks, ESLint, Ruff and repository Prettier. The first combined Python invocation passed 432 but encountered 40 browser setup failures/errors because another evaluation run already owned the local ports; that evaluation run completed with 92 passed in 392.22s, and all seven new focused regressions passed (including the final additional export-failure case). No application fix was needed for the port collision. Document links and both confusion-matrix renderings were checked.

CAP-02 final release and CAP-03 final evaluation remain open. Next: establish a feasible independent evaluation/label-review arrangement and separately authorize any same-input LLM comparison; CAP-04 cloud design decisions can proceed alongside those gates. No paid inference, spending-cap change, cloud provisioning or push occurred. Preserve unrelated working-tree edits and the existing MVP tag.

## CAP-02 coverage expansion prepared; no new fit or freeze

The owner approved the dataset-first next step. [The coverage plan](docs/cap02-expansion-plan.md) and [review](docs/cap02-expansion-review.md) accompany 168 new synthetic/exposed draft records: 160 intent candidates (four per intent/language cell) plus eight contextual fragments excluded from text-only classification. Combined with the original 140, the pool contains 308 records and 263 provisional primary candidates. This is not independent human data or an unseen set.

Review merged equivalent clear-cart scenarios, retained 15 known cross-source links and replaced twelve name-substitution drafts with ordinal/cart-line/shortlist-price product resolution tasks before training. Prior authored wording is archived. The expanded graph preserves all old components and all related turns: 41 provisional components, largest 128. All ten intents now have multiple components, but `mutate` has three rather than the desired four. No new split is assigned. Full legacy/private-source overlap adjudication and this allocation limitation must be settled before a new frozen pilot. The existing freeze command still reconstructs pilot 1 only.

Verification: v2 schema, 308 unique IDs/normalized texts, four-per-cell counts, all context hashes and antecedents, transitive membership, 212 catalogue identity/variant/line-key/price checks, repository formatting and seven offline experiment regressions passed. Spec review corrected three substantive annotation errors plus a stale scenario tag; Standards review corrected two grouping issues. Rechecks found no unresolved annotation findings. These are AI draft reviews, not independent human gold. The full runtime suite was not repeated for this data-only change.

The first pilot's sources, frozen release, protocol and results remain unchanged. No runtime code, prompt, phrase rules, training, paid inference, cloud resources, spending limit or remote repository changed. CAP-02 final release and CAP-03 final evaluation remain open. Unrelated working-tree changes are preserved.

## CAP-01 exports and synthetic CAP-03 pilot prepared — 2026-10-06

The owner approved a synthetic development pilot while explicitly keeping final evaluation open. [The protocol](docs/cap03-pilot-protocol.md), [annotation review](docs/cap02-annotation-review.md) and [results](docs/cap03-pilot-results.md) record 140 synthetic messages, 103 eligible cases, 37 exclusions and a frozen 82-training / 21-validation / zero-unseen release. All 15 conversation/paraphrase components remain intact. AI-reviewed draft labels are not independent human gold; the final CAP-02 split placeholder remains unfrozen.

Twelve offline TF-IDF/Logistic Regression configurations converged. Selected word 1–2 grams, C=0.1, balanced weights: 4/21 validation correct (19.05%), ten-label macro-F1 0.1024. Strong class imbalance and four absent validation classes limit interpretation. This is selected-on-validation development evidence, not an unbiased test result or an LLM comparison. All trials, per-case predictions, plots and source hashes are retained. The model is offline-only; no application runtime, prompt, phrase rules or provider configuration changed.

The [three CAP-01 PDFs](docs/cap01-export-readme.md) and [editable one-slide infographic plus 2560×1440 PNG](output/infographic/README.md) are exported for AWS ML Engineering. The PDFs preserve the 2 October source dates and pending lecturer record; all 23 pages were inspected. The [CAP-04 AWS brief](docs/cap04-aws-design-draft.md) proposes a supervised single-host demo with cost, access, reset and safety decisions explicit. It is not an approved deployment.

Verification: 465 Python tests (including seven new offline experiment checks) passed in 406.14s; 155 TypeScript tests, workspace builds/typechecks, ESLint, Ruff and repository Prettier passed. Independent Spec and Standards reviews found three experiment-integrity/reporting issues; all were fixed and rechecked, with zero unresolved findings on either axis. Frozen-release/source hashes, artifact hashes, document links and staged credential-pattern checks passed. PDF/PPTX files are marked binary in Git to preserve exported bytes.

CAP-01 still needs owner/lecturer review and the Skills Dynamix organization-repository invitation; no official upload is claimed. CAP-02 final unseen release, CAP-03 same-input LLM comparison and CAP-04 account/Region/model/budget/access decisions remain open. Next: expand independent conversation families and review labels before a new experiment version; do not repair this frozen release after seeing scores. No paid inference, AWS account access, provisioning, budget increase or push occurred. Preserve unrelated working-tree edits and the existing MVP tag.

## DEPI guidelines mapped; CAP-01 drafts aligned — 2026-10-02

The owner supplied five DEPI PDFs and confirmed the official track name **AWS ML Engineering**. The [alignment register](docs/depi-guideline-alignment.md) maps their requirements and unchanged DEPI dates. Official submission is through a Skills Dynamix organization repository; its invitation/URL remains unprovided. The newer Literature Review heading retains older Lecturer Review bullets, so the research synthesis is preserved alongside a separate pending lecturer-feedback/approval record. No grading weights or approval were invented.

Planning now includes proposed Gantt windows, actual resource constraints and KPI definitions; requirements include user stories and acceptance mapping. The [design supplement](docs/system-design-views.md) adds use-case, context/detail DFD, activity, class, local-deployment and schematic wireframe views. It reflects the session refactor and current in-memory/shared Storefront state; AWS decisions remain CAP-04 work. The [infographic brief](docs/project-infographic-brief.md) uses the confirmed track and verified content; a final slide/image has not been exported.

Verification: all 13 Mermaid diagrams across planning and design parsed/rendered; document links and formatting checked. Standards review found no actionable issues; Spec review found an omitted final-attendance checklist item and a misleading read-only activity branch, both corrected. This is documentation-only; no fresh application test run, paid model call, remote change, upload or push is claimed. Existing unrelated working-tree edits are preserved.

Next: owner reviews the aligned package; obtain lecturer evidence and organization-repository access/export conventions; produce final submission exports and infographic. Final discussion attendance is required, but its actual appointment remains unconfirmed. CAP-01 is not officially submitted, CAP-02 remains open with exposed synthetic drafts, and CAP-04 remains open for cloud decisions.

## CAP-02 synthetic development collection prepared — 2026-10-02

At the owner's request CAP-02 remains open and active. The [development batch](eval/datasets/capstone-v1/development/README.md) contains 40 assistant-generated draft records: ten Egyptian Arabic, ten Franco-Arabic, ten English and ten mixed. Record format 2 adds explicit cart/mutation operations, catalogue requirements and semantic notes without changing runtime schemas. Thirteen hashed synthetic context fixtures preserve referents and conversation states. A grouped 32-training/8-validation/0-unseen proposal is tentative; actual release assignments remain empty.

The owner confirmed the supplied 100-message file was generated by Gemini. Its [intake record](eval/datasets/capstone-v1/development/intake/README.md) preserves the original bytes and labels separately, with provenance and annotation gaps. It is not merged or approved for training. Both batches are synthetic/exposed; 140 draft messages is not a count of reviewed, independent or unseen examples. No participant observations or unseen evidence were invented.

Verification: 40-record shape assertions, runtime label/Constraint vocabulary, ten-per-language counts, unique IDs/text, context hashes/predecessors, grouping isolation and the draft 32/8/0 allocation passed. The Gemini original checksum matches. Independent AI Spec/Standards reviews of the 40-record draft found no actionable issues; they do not constitute independent human label approval or review of the separate Gemini intake. Formatting is checked separately. Application tests were not rerun for this data/documentation-only change; no paid model calls, training, runtime changes or push occurred.

Next: map the Gemini labels with context and explicit constraints, review cross-source paraphrase groups and labels with the owner, then resolve release validation and honest held-out evaluation arrangements before CAP-03. CAP-02 is not closed or frozen.

## Session modularity refactor completed; actual working arrangement — 2026-10-02

The owner clarified that only the owner and coding assistant actively perform the work; nominal team members are not available contributors. Do not request their help, infer contributions from role titles or depend on independent human review that does not exist. The assistant took over the session refactor. CAP-02 is deferred and incomplete: its preparation/inventory is ready, but new collection, reviewed labels, release validation and frozen splits are absent. It was not closed under the owner's conditional request.

The [refactor record](docs/session-modularity-refactor.md) describes the preserved interface and new modules. `agent/sessions.py` shrank from 1,822 to 203 lines; session registry/state, SSE delivery, interpretation, shopper commands, ActionResult handling and recovery now have distinct modules with explicit composition. Original public method signatures/domain imports remain; no mixins, dynamic dispatch, new shopper phrase rules, prompt edits or feature changes. The large ActionResult method remains a documented future extraction opportunity rather than being rewritten in this pass.

Runtime commits: `b47ea0d` registry/state, `46a941d` SSE adapter, `7df44d9` task modules. Each stage passed the unchanged **458-test Python suite** (395.80s, 389.86s, 388.99s). **155 TypeScript tests**, workspace builds/typechecks, ESLint, Ruff and repository Prettier passed. AST comparisons and independent Spec/Standards reviews found no unintended logic/signature changes. No paid model calls or budget changes occurred; the MVP tag and unrelated work remain untouched. These changes are committed locally; no push occurred in this refactor turn.

Next: review the refactor at its new module interfaces, then decide a feasible owner/assistant CAP-02 collection and evaluation protocol with honest independence limitations. Do not silently convert exposed/synthetic examples into unseen evidence. The earlier System Analysis & Design independent review remains separate and pending.

## CAP-02 initiated; academic document leads confirmed — 2026-10-02

CAP-02 is active with [collection/permission guidance](docs/cap02-collection-packet.md), a [current label guide and legacy coverage audit](docs/cap02-label-guide.md), and an explicit exposure inventory under eval/datasets/capstone-v1. All 104 legacy source-case references and 89 pinned development/test sources are exposed; these are not 104 independent utterances. No new human data, independently reviewed labels, training or frozen splits are claimed. Unseen custody, independent review, contributor capacity and permission arrangements remain unconfirmed; unseen content must stay outside the development checkout/chat. Release validation and freeze remain outstanding.

The owner confirmed academic leads: Mohamed Hamdi for Planning & Management, Ahmed Yasser for Literature Review and Rana Ali for Requirements Gathering, due 16 October. The owner coordinates submission; template/location remain unprovided. Dataset custody and model-training ownership are separate and pending. The owner is handling the first session-management refactor slice; this work changed no runtime, prompt, original corpus or session file.

Verification: all 89 pinned source hashes, 104 case identities/exposure markers, historical source hashes, documented label counts, empty unfrozen splits and non-evaluable template were checked. Changed Markdown/JSON formatting and relative links were checked. Independent CAP-02 Spec and Standards reviews reported no actionable findings. Application tests were not rerun for this documentation/data-inventory change; no paid calls or cloud operations occurred. The earlier System Analysis & Design independent review is still pending and is not covered by these CAP-02 reviews.

## System Analysis & Design drafted ahead of 6 November — 2026-10-01

The [design document](docs/system-analysis-design.md) now records the implemented local system: actors/use cases, component and trust boundaries, execution/Confirmation sequences, task states, logical data model, interfaces, failures and requirements/evidence mapping. It explicitly identifies the Storefront's shared in-memory cart and loss of server state on restart; separate Agent sessions do not imply isolated carts.

The local-system content is prepared for review. Final graduation design still needs CAP-04's costed AWS service selection, region/model access, budget, audience/access policy, state isolation and restart/storage decisions. CAP-04 remains open; no runtime change, paid model call, cloud provisioning or deployment is claimed. Independent Spec and Standards reviewers were attempted but both hit the account usage limit; their review is incomplete. Documentation formatting and local-link checks are the validation for this change; application tests were not rerun.

## CAP-01 drafts prepared; owner coordinates submission — 2026-10-01

Three review drafts are prepared for the confirmed **16 October 2026** deadline: [planning and management](docs/cap01-project-planning.md), [literature review](docs/cap01-literature-review.md), and [requirements/traceability](docs/cap01-requirements.md). The literature review synthesizes seven primary sources with citations; external findings, project rationale and planned experiments are distinguished. No model training, dataset collection, paid inference or cloud provisioning occurred.

The owner will coordinate the overall submission. Additional academic assignments, literature ownership, unseen-data custody and classical-training ownership remain pending at his explicit request. DEPI has not supplied an official document template or submission location; these remain unconfirmed. Existing technical roles and DEPI dates are preserved. CAP-01 remains in progress for team review and submission-readiness work; these documents are not submitted or instructor-approved. The [execution register](docs/cap01-execution.md) links the current drafts and supersedes stale preparation wording in older local documents.

Verification is documentation-only: changed Markdown formatting, relative-link checks and independent Spec/Standards review. No fresh application test run is claimed because runtime behaviour did not change. Preserve the existing local MVP tag and provider cap; CAP-02/03 experiments have not started.

## CAP-01 active: team allocation and DEPI deadlines confirmed — 2026-10-01

Local MVP tag `mvp-1` points to `39ac6d1`; Ticket 16 is closed under the two explicit owner-approved adjustments documented in RESULTS.md. CAP-01 is now active; [the execution register](docs/cap01-execution.md) is authoritative over older notes that called the schedule or team unconfirmed.

The owner supplied the five roles: Ahmed Yasser (AI Agent/LLM architecture), Ali Amr (AWS infrastructure), Mohamed Hamdi (backend/orchestration), Ezz Mohamed (frontend/Storefront integration), and Rana Ali (QA/safety/evaluation). Contact addresses were excluded from Git. The owner explicitly selected **DEPI**, not Industry: planning, literature and requirements due **16 October 2026**; design **6 November**; implementation **30 November**; final presentation/testing/reports **4 December**.

Next: prepare the three 16 October documents against the real local-MVP evidence and assign the remaining academic coordination, literature, unseen-data custody and classical-training responsibilities. Official submission templates/location and rubric remain unprovided. CAP-02 data and CAP-03 training/comparison remain later steps; no new paid experiment, cloud resource or external submission is authorized by this handoff.

## Local MVP closed; CAP-01 is next — 2026-10-01

The owner explicitly approved Ticket 16 as an informal qualitative study: five positive reactions to advice, two reported successful account navigations, and the two original advice findings. No formal task success rate, ratings, interface-confidence classification or extra findings were invented. The owner separately approved using historical Ticket 15 live acceptance, the current full automated suite and final targeted advice/cart checks, without repeating the three full live runs on this release. Both adjustments are recorded in [the closeout](docs/ticket16-closeout.md).

Final verification used eight messages/fourteen provider calls at **$0.0204672**. Advice/navigation passed; cart add initially failed with a navigation-only product ID on cart intent. `intent-v28` adds schema-specific repair guidance without phrase rules or weaker guards; a restored-context live recheck added the exact variant/quantity and preserved other cart lines. Original failures, residual grounding limitations and the unreached live clear probe remain explicit. **458 Python and 155 TypeScript tests passed**, with builds/typechecks, lint, formatting and independent reviews. The key cap remains $1.00 Never, with $0.051541498 remaining at the post-check read-only observation.

Ticket 16 is closed on this approved basis; **`mvp-1`** identifies the local release. [RESULTS.md](RESULTS.md) distinguishes historical full-model evidence from current targeted/regression evidence. Next is CAP-01 graduation planning, followed by reviewed CAP-02 data and offline CAP-03 comparison. No cloud deployment, production readiness or independent-store compatibility is claimed.

## Exact catalogue matches now receive grounded explanations — 2026-10-01

The owner manually reported that advice made the Copilot conversational and requested explanations for exact matches, especially multiple options. Schema 9 catalogue discovery with exact results now uses the existing read-only advisor even in browse mode. Prompt `advice-v3` asks for concise reasons tied to verified facts and Shopper priorities, conditional comparisons and honest uncertainty. Product cards and eligibility remain authoritative; ordinary filter navigation, schema 8 and zero-exact browse paths are preserved. No phrase matching or execution-guard change was added. See [behaviour and verification](docs/conversational-advice.md#exact-match-explanations--2026-10-01).

Verification: **457 Python tests passed**, including single/multiple exact results, invalid-advice fallback and Stop/refresh regressions. All **155 TypeScript tests**, builds/typechecks, lint and formatting passed. Independent Spec and Standards reviews found no actionable issues. These scripted checks verify routing and guards, not generated prose quality. No paid calls, cap changes or provider-account edits occurred. Each newly explained discovery adds one bounded advice call; budget/provider failure retains verified cards and the existing fallback. Ticket 16 remains open and prior live failures remain recorded.

## Ticket 16 feedback recorded; bounded advice exploration found a transition failure — 2026-10-01

The owner clarified that the five informal testers explored without his help, until satisfied. Two advice-related findings are recorded in [the feedback ledger](docs/ticket16-feedback.md). Required task coverage, digital-confidence eligibility and explicit benefit votes remain unknown; no missing measurements or additional participant findings were invented.

A bounded synthetic exploration used eight messages and fourteen provider calls at **$0.0203128**. Styling, budget correction and acknowledgement of unknown fabric quality worked, but opening a recommended product failed because the model copied discovery preferences into navigation. Grounding weaknesses also appeared for an owned garment and unsupported suitability. Original failures and provenance are retained in [the live evaluation record](docs/ticket16-advice-evaluation.md). Cart-action probes were not reached; this is not an advice-to-cart acceptance pass.

Prompt `intent-v27` scopes preference carry-forward and discourages unsupported semantic substitutions; `advice-v2` reinforces uncertain comparisons. Typed cross-field repair now distinguishes navigation from discovery and preserves valid shopping requirements. No phrase matching or relaxed Action guard was added. Full Python suite: **445 passed**; after the final review correction, **47 focused tests passed**. All **155 TypeScript tests**, builds/typechecks and lint/format checks passed. Independent Spec and Standards reviews have no remaining actionable findings. Live post-change effectiveness remains unverified.

The key remains **$1.00 total, reset Never**, with **$0.090200198 remaining** at the post-run read-only check. No cap increase, auto top-up or additional deposit occurred. The announced eight-message budget is consumed. Next is a separately bounded live recheck and reconciliation of Ticket 16 participant evidence; Ticket 16 stays open, and CAP-03 remains queued behind local closure and CAP-02 data. This section supersedes older pending-evaluation/status wording below without rewriting historical evidence.

## Conversational advice implemented; live quality evaluation pending — 2026-10-01

The owner prioritized conversational styling and decision help after feedback from five informal testers. The laptop example did not expand the catalogue, and UI work is out of scope. This owner-reported feedback does not establish completion of the Ticket 16 study protocol or change graduation gates.

Prompt `intent-v26` requests schema 9 (schema 8 execution compatibility remains). A separate read-only `advice-v1` step receives fresh bounded catalogue evidence, conversation and session preferences. It can explain trade-offs, give styling opinions and ask useful questions; execution still uses the existing target, inventory, bounds, Confirmation and replay guards. No shopper phrase interpreter was added. Advice cannot emit Actions, and late results after Stop/recovery are discarded. See [design, evaluation probes and verification](docs/conversational-advice.md).

Verification: the full Python run had 440 passes and two benchmark comparison failures caused by the new empty optional field. After fixing that normalization and review findings, all 374 affected Agent/intent-benchmark tests passed. Browser checks passed in the full run; all 155 TypeScript tests, builds/typechecks and lint passed. Independent Spec/Standards findings were fixed and rechecked. These scripted checks verify flow and safety, not live advice helpfulness.

No paid calls, key-cap changes or new deposit occurred. Live advice quality remains unmeasured; the previous Ticket 15 acceptance belongs to its frozen runtime. The last known allowance remains $0.115626878 under the $1.00 non-resetting cap. Next is a separately budgeted conversation-quality evaluation and completion of Ticket 16 evidence, not capstone execution.

## Ticket 15 complete; Ticket 16 is next — 2026-10-01

The single owner-authorized replacement acceptance set passed the unchanged gate in all three consecutive runs: **43/44, 44/44, 44/44**, with **19/19 designated safety cases passing each time**. The frozen runtime was commit `dd4d897`, prompt `intent-v25`, schema 8 and OpenRouter `google/gemini-2.5-flash`. All latency, efficiency and measurement gates passed. See [the full replacement results](docs/ticket15-replacement-results.md); the prior September 28 reports remain unchanged and separate.

Run 1's mixed-language filter failed and remains recorded. Its failed provider stream had a saved generation ID; a read-only accounting GET matched that exact ID and model and reported zero tokens and zero cost. Those provider values were recorded in a separate reconciled report with original-hash provenance. No failure was replaced with a focused rerun, no unknown value was guessed, and no threshold was lowered. The original failed-measurement set was not retroactively declared accepted.

The replacement set has **$0.17610546** in provider-reported/reconciled call cost. The key cap remains the explicitly authorized **$1.00 total, reset Never**, with **$0.115626878 remaining** at the post-run read-only check. The observed key-allowance reduction was $0.170991580; that account-level delta is recorded separately from per-call usage rather than substituted for it. No new deposit, auto top-up or additional replacement set was performed. No hardcoded shopper phrases were added; interpretation and target selection remain with the LLM.

Verification: full Python suite **423 passed**; final affected subset **44 passed** after cancellation/redaction and authorized-cap regressions. All **155 TypeScript tests** and builds passed, with Ruff lint/format, ESLint and staged-document formatting checks. Independent Spec and Standards review findings were fixed and re-reviewed. Recorded source hashes and reconciliation-only changes were verified. Tests and live evidence are distinct; passing this fixed corpus is not a guarantee for all wording.

**Next: Ticket 16**, the prepared five-person uncoached study, including two participants with limited digital confidence. Recruitment, facilitator assignment, consent and an explicit study budget still need to be arranged before sessions. Do not tag the local MVP or start substantive capstone execution until Ticket 16 closes. The approved Controlled Storefront AWS capstone and offline ML backlog remain queued under `docs/graduation-scope.md`.

## Ticket 15 telemetry prepared; one replacement acceptance set authorized — 2026-10-01

Implemented prospective OpenRouter attempt UUID/UTC/generation-ID retention, usage capture before rejecting error events, and a durable redacted evaluation journal. Cancellation closes the provider iterator before journaling, and schema diagnostics exclude untrusted paths/messages/free text. A read-only exact-generation reconciliation command preserves originals, records provenance and leaves unknown or conflicting accounting unresolved. No language interpretation, acceptance threshold, provider cap or credentials changed. See [telemetry evidence and replacement-run plan](docs/ticket15-telemetry-retention.md).

The original three report hashes remain unchanged. A separate historical reconciliation still reports 44/44 tasks and 19/19 safety cases for run 3, with measurement completeness failing because its missing attempt has no saved generation ID. No guessed accounting or paid replacement calls were used. The owner authorized exactly one replacement three-run set and raised the total key cap to $1.00, reset Never. A read-only check verified that setting and $0.286618458 remaining before the run. No additional deposit or automatic top-up is authorized; do not run further replacement sets without permission.

Verification: full Python suite **423 passed**, all **155 TypeScript tests** and builds passed. Final focused telemetry/acceptance recheck **35 passed**, including three cancellation/redaction regressions added after the full suite was collected. Ruff lint/format, ESLint, changed-document Prettier and diff checks passed. Independent Spec and Standards reviewers rechecked their fixed findings with no remaining actionable issues. Ticket 15 remains open pending complete live evidence; the approved graduation roadmap below is unchanged.

## Voice availability clarification — 2026-09-29

The owner reported that OpenRouter recording had disappeared. The running `/speech/availability` endpoint returned false; a read-only key check showed $0.036618458 remaining under the unchanged $0.75 non-resetting cap, below the existing $0.50 audio minimum. The Panel silently returned on unavailable recording and only showed the browser speech failure. It now explains that OpenRouter transcription is unavailable and directs the owner to service/key allowance checks, typing or browser speech in Chrome. A regression verifies that the explanation appears without requesting microphone access. All 32 Panel tests, Panel build/typecheck and repository ESLint passed. No provider transcription was attempted.

The owner explicitly chose to **keep the $0.75 cap** and use typing or try Chrome speech. OpenRouter transcription therefore remains unavailable under the current allowance; do not claim this message change restores paid audio or raise the cap. Ticket 15's measurement gap below remains open.

## Ticket 15: behavior passes; measurement gate pending — 2026-09-28

Three consecutive real-model/browser runs passed **44/44, 44/44 and 44/44** messy-language scenarios, with **19/19 designated safety cases passing in each**. They exercise Egyptian Arabic, Franco-Arabic, mixed language, typos, fragments, corrections, ambiguous variants, negation, cart changes, navigation, mobile/SPA behavior and recovery. Assertions check exact cart contents and actual page/Spotlight outcomes. Browser Action median was 306–310 ms; all seven fully specified filters used one Action and navigation median was one Action. Model-inclusive first-Action median was 2.5–2.8 seconds, reported separately.

**Ticket 15 remains incomplete:** run 3 has one rejected model stream with no recorded token/cost usage (`orders-login`); its retry and actual task succeeded. Runs 1 and 2 pass every gate, but run 3 correctly fails measurement completeness. Do not mark the ticket complete or substitute zero for unavailable usage. No further paid reruns were made. Raw reports, including earlier failures, are retained under ignored `eval/reports/`; see [the committed results](docs/ticket15-results.md) and [evaluation contract](docs/ticket15-evaluation.md). The final source hashes were verified against the reports.

Runtime repairs give the model precise missing-field/schema feedback and current executable cart button IDs on its one allowed repair attempt. A complete discovery proposal missing its category is repaired or becomes a useful clarification. Prompt `intent-v25` retains model ownership of language, negation, quantities and target selection; no shopper phrase matching or dictionary interpreter was added. All origin, target, quantity, Confirmation and replay guards remain. Streaming is opt-in for evaluation to measure TTFT; output is fully buffered and validated before the Agent can act. Normal application requests remain non-streaming.

Independent Spec and Standards review findings were fixed. The final follow-up hit reviewer usage limits; the last narrow changes were reviewed locally. Preserve this limitation rather than claiming final independent sign-off. The unchanged non-resetting $0.75 key cap has **$0.046856858 remaining** at the final read-only check. The allowance decreased by about **$0.4881** during Ticket 15 development and evaluation, including failed experiments; the final three runs alone have $0.16271332 recorded cost plus one unknown attempt. Do not automatically increase the cap or run another paid suite.

Final verification: **410 Python and 155 TypeScript tests passed**, including the complete scripted browser suite. Repository Prettier, ESLint, Ruff lint/format and all builds passed. These local checks make no paid model calls. Verification was finalized on 2026-09-29; the recorded live runs above are dated 2026-09-28.

**Next:** resolve the remaining measurement evidence for Ticket 15 before declaring its gate closed, then Ticket 16's five-person uncoached study. A passing fixed corpus does not prove every phrase works. Independent-storefront work, architecture splitting and AWS remain deferred. Preserve ignored credentials and unrelated proposal documents. Earlier sections below are historical and do not override this frontier.

## Ticket 14: SPA execution — 2026-09-27

The owner accepted cleanup commit `d7f6d12` and explicitly resumed Ticket 14. The ticket is implemented with opt-in URL-backed and component-only SPA variants at the same category, cart and account destinations. The Bridge observes client-side history and DOM changes, waits for loading and optimistic updates, verifies controlled input values, drops detached targets, and reports same-document navigation results. The Agent distinguishes applied filters from URL shortcuts and falls back to visible controls. SSE reconnect honors the last event cursor and the Panel suppresses repeated events. No shopper-language interpreter, provider change or architecture split was added.

Final verification: **398 Python and 155 TypeScript tests passed**, including the complete browser suite; repository-wide Prettier, ESLint, Ruff lint/format and all builds passed. The first full run caught delayed committed selections reaching the Agent with old values; the fix preserves immediate ready-page change snapshots alongside settled observations. An old mobile fixture was updated to check the Stop handback instead of wording removed by `d7f6d12`. Review also fixed failed SPA fetches being reported as successful navigation. The complete Python suite was rerun after these fixes. Standards and Spec were reviewed locally; no independent sub-agents were used in this side conversation.

The same discovery task took one Action in URL mode and three in component mode, with identical filtered results. Browser coverage includes back/forward, late DOM changes, exact cart Undo after refresh, expired/new Confirmation, duplicate delivery without duplicate cart writes, stale targets, off-origin blocking, and failed loads. See [Ticket 14 evidence](docs/ticket14-spa.md). These are controlled execution tests, not additional live-model language evidence. No paid model calls were made; the $0.75 total non-resetting cap and credentials are unchanged.

All three local services were restarted with the current code and the original two-line cart was restored and compared exactly. Open http://localhost:4100/?spa=url or http://localhost:4100/?spa=component to test; `?spa=off` returns to ordinary navigation. Unrelated proposal files are untouched. **Next: Ticket 15, the complete local evaluation gate.** Older sections below are historical and do not override this frontier.

## Exploratory user-flow acceptance — 2026-09-26

Before further owner testing, a bounded real-model/browser exploration exercised ambiguous same-product variants, changing a quantity decision, negated selective removal with Undo, cancelling bulk clear, oversized quantities, vague references, self-correction, material exclusions with a budget, and misspelled navigation. The initial run passed six of eight cases (nine submitted requests). It exposed two real failures: arbitrary size selection and an invalid quantity presented as a model-format error.

Prompt `intent-v20` now receives separate observed cart rows and product memory retains both variant labels. The model owns interpretation and ambiguity; no shopper phrase matching was added. Finite fractional/out-of-range quantity proposals reach runtime bounds validation, which asks for a whole quantity from 1 to 99 without dispatching a mutation or spending a repair call. Safe clarification proposals remain questions before target planning.

Focused live reruns passed both failures: the three-request ambiguous-size/answer/change-of-mind sequence affected only the selected line, and the 1,000-unit request asked a useful quantity question without changing the cart. There were 13 submitted requests across the exploration and focused reruns; provider repair attempts are not included in that submission count. Original failures and focused results remain separate in ignored `eval/reports/exploratory-user-flows*.json`. This was not a clean all-cases rerun or an exhaustive language guarantee. Repeat with `LLM_EXPLORATORY_EVAL=1 python -m eval.exploratory_live`; the runner caps submissions at 12, permits a focused case selection, checks task-specific events and exact cart contents, and restores the starting cart.

Independent Spec and Standards reviews found no remaining runtime issue. The Standards review caught missing report-directory creation on a fresh checkout; it was fixed before final verification. Ticket 14 remains on hold. Preserve the $0.75 total non-resetting provider cap, credentials and unrelated proposal files.

Final verification: **383 Python and 150 TypeScript tests passed**, including the complete scripted browser suite. Repository-wide Prettier, ESLint, Ruff lint/format and all builds passed. Updated services are running at http://localhost:4100 and the original local cart has been restored. No further paid model calls were made for the full checks.

## Product continuity and conversation acceptance — 2026-09-26

Manual testing found a remaining hardcoded eligibility rule: product opening was restricted to the immediately preceding recommendation batch, even when a product link was currently visible in the cart. The session also discarded recommendations across unrelated completed tasks. The exact cart-to-shirt return failed in a live reproduction with `Product ID was not among verified recommendations`.

Prompt `intent-v19` now receives up to 24 observed product identities, the latest recommendation batch separately, and a bounded recent conversation (12 entries, 500 characters each). A shared product-identity check accepts verified recommendations and same-origin product routes from observed links/current product pages. Accepted Action Results and reconciliation snapshots also contribute identities; repeated links preserve their product group instead of generic detail labels. Context is scoped to the session and origin. Live tasks retain their starting origin, and cannot answer/Retry into a different origin with cached identities or conversation. No shopper phrase matching was added. The field schema explicitly distinguishes requested quantity deltas from final values; duplicated prompt context was removed.

Independent Spec and Standards reviews found the repeated-link, observation-retention and active-task origin gaps; all were fixed and rechecked. Fifteen HTTP regressions cover product opening without recommendations, returning after cart/navigation/new recommendations/refresh, observed browse results, repeated links, and negative origin/session/unknown-target cases. These are execution-contract tests with explicit model outputs, not language-quality evidence.

Real-model evidence: the initial conversation run caught an incorrect quantity outcome and a test-harness mismatch against a bilingual heading. After clarifying quantity field semantics and correcting the heading assertion, both complete conversations passed (eight submitted requests): exact multi-item quantity increase, shirt opening/return, and reopening an earlier recommendation after a different recommendation batch and a manual page change. The original failed report is retained under ignored `eval/reports/conversation-live-initial.json`; the passing run is `conversation-live.json`. This sample does not establish universal wording reliability. Use `LLM_CONVERSATION_EVAL=1 python -m eval.conversation_live`; it bounds each run to eight submitted turns and restores the starting cart in cleanup.

Final workspace verification: **378 Python and 150 TypeScript tests passed**, including the full scripted browser suite. Repository-wide Prettier, ESLint, Ruff lint/format and all builds passed. Updated services are running at http://localhost:4100 and the original local cart has been restored. Ticket 14 remains on hold; the owner's initial reported cart fixes now work, but broader acceptance is still underway. Preserve the $0.75 total non-resetting provider cap, credentials, and unrelated proposal files.

## LLM/runtime boundary repair — 2026-09-26

This section supersedes earlier claims that validation did not hardcode Arabic phrases. The audit found a second interpreter inside validation; those claims were incorrect. The live path now requires schema 8 / prompt `intent-v18`: the LLM interprets wording, negation, quantities and references against the current sanitized Snapshot, and proposes observed cart target IDs. Runtime validates supported capabilities, bounds, target validity, freshness and execution authority without reinterpreting shopper phrases. Cart edits begun outside the cart return to the model after fresh cart navigation. Exclusions are explicit; known forbidden materials are rejected and unknown material data is disclosed as unverified.

The legacy scripted test interpreter and controlled-store selectors remain explicitly separate from live interpretation. `/step` is disabled for live providers. Ranking and localized explanation templates remain deterministic; arbitrary storefront generalisation is not included. See [the boundary contract](docs/llm-runtime-boundary.md) and [the historical audit](docs/hardcoding-audit-2026-09-26.md).

Independent Spec and Standards reviewers reran successfully and verified fixes for property-kind checks, live schema downgrade and scripted endpoint isolation. The initial ten-case real-provider interpretation run passed nine; the model's safe variant clarification was rejected by an unnecessary schema requirement. After fixing that requirement, the focused ambiguity rerun passed. This is limited language evidence, not a guarantee for all wording. Automated model fixtures verify execution contracts, not language quality.

Final workspace verification: **359 Python + 150 TypeScript tests passed**, including the browser execution and safety regressions. Repository format, lint and builds passed. The first full run exposed four old-schema test fixtures; they were migrated to schema 8, then the complete Python suite passed. Tests that enforced lexical interpretation were retired rather than preserving the rejected design. Live browser execution passed quantity, removal and confirmed clearing on a two-product cart. Add initially exposed the schema rejecting an explicit `set` quantity on the product form; schema 8 now defines add/set as units to add (never a final cart total), while rejecting incompatible delta modes. The final 324-test Agent/evaluation subset and independent 17-test boundary review passed after that change. A focused live add rerun completed and Undo restored the exact cart; other reversible operations also passed exact Undo, and bulk clearing remained unchanged until bound confirmation. The full workspace suite was run before this final narrow add-schema change; its affected checks and actual browser flow were rerun afterward. Updated services are running at http://localhost:4100 and the saved local cart was restored. Ticket 14 remains on hold until owner manual acceptance. Preserve the $0.75 total non-resetting OpenRouter cap, credentials and unrelated proposal files.

## LLM draft self-repair — 2026-09-26

Ticket 14 remains on hold. Manual testing showed that a clear named cart request could receive a transient invalid Structured Intent and enter a Shopper rephrasing loop. The Agent still delegates interpretation to the configured LLM; no command phrases, product names, or cart decisions were moved into a deterministic parser. A rejected model draft now gets one bounded LLM reconsideration of the same Shopper request. The second draft receives the complete schema and must pass every existing grounding, quantity-direction, cart-line, mutation, navigation, and safety check before it can issue an Action.

If both drafts fail, the task pauses without a browser Action and offers the existing Retry/Stop recovery instead of blaming the Shopper or repeatedly asking for a clearer sentence. Manual Retry preserves the original request and current Snapshot. Prompt-override requests are rejected before a provider call. A live diagnostic of the exact `زودلي 3 كمان من قميص رسمي` request produced a valid quantity/increase/3 decision; it cost **$0.0014027**. The non-resetting key limit remains $0.75, with $0.643938956 reported remaining after verification.

Verification: **150 TypeScript + 439 Python = 589 tests passed**. Repository-wide Prettier, ESLint, Ruff lint/format, and all builds passed. The first browser-suite attempt collided with already-running manual services and was stopped; the clean isolated scripted browser run then passed all 53 cases without provider calls. No safety validator was removed or bypassed. Independent Standards and Spec reviews found no remaining actionable issue after malformed-provider-response and duplicate-retry findings were fixed.

## Cart conversation repairs — 2026-09-26

Ticket 14 remains on hold. The owner's exact `عايز 3 كمان من تيشرت اسكندرية` produced a correct live quantity/increase/3 intent that our verb whitelist rejected. Quantified relative requests now preserve the explicit amount and direction. Shared conservative name normalization handles `تيشرت اسكندرية` against `تيشيرت إسكندرية`; `وديني` is recognized as opening. Quantity/removal requests outside the cart navigate there and plan from a fresh same-origin Snapshot.

Fractional browser scroll offsets now round at Snapshot production. Failed result delivery no longer leaves the Panel silently busy; it blocks replay and asks the Shopper to inspect the cart and Stop. A full browser run exposed another race: initial cart hydration detached unchanged server-rendered controls after the Bridge observed them. Identical markup now preserves controls. Invalid model drafts get one rephrasing attempt, then a Stop handback instead of a repeated question loop.

Evidence: 150 TypeScript tests passed; full Python run had 423 passes and one failure exposing the hydration race. After fixing it, all 10 cart browser tests passed, plus the final 59-test affected Agent subset (including 17 new conversation tests). Full Python was not rerun after the focused repair. Format, lint, typechecking and builds passed. Independent review findings on relative direction and off-origin test coverage were fixed; final review was clear. Live exact opening, add with completion, and increase from 1 to 4 passed. The live recommendation setup still unnecessarily asked for an already supplied 500 EGP budget; this separate coverage issue remains open. Do not claim general language reliability or a fully accepted MVP. See `docs/superpowers/plans/2026-09-26-cart-conversation-repair.md`.

The $0.75 total non-resetting API cap and credentials are unchanged. Unrelated proposal files are untouched.

## Recommendation follow-up and interpretation recovery — 2026-09-26

The owner's sister's `افتح صفحة القميص الرسمي` failure was reproduced with the live provider: it selected the correct verified product but omitted redundant `navigation_source` metadata. Product opening now grounds the requested name against verified suggestions and current Shopper words, normalizing Arabic definite articles and diacritics. Missing model quotations no longer veto an independently grounded request. Ambiguous references ask which verified product to open; an exact answer resolves locally without another model call. Locate requests, negation, conflicting names and unknown IDs cannot silently authorize navigation.

More generally, an unusable model draft now produces an editable clarification question instead of a Retry loop. Its unvalidated execution authority is discarded, and the answer starts a fresh interpretation with verified recommendation context. Repeated failures reach a working Stop at the task limit. Provider/budget failures retain their existing paused flow. Bound Confirmation, stale-answer rejection, origin checks and uncertain-mutation recovery remain enforced. This is graceful recovery for unseen failures, not a guarantee of perfect language interpretation.

Verification: the complete workspace run passed **148 TypeScript and 413 Python tests**. Review then added three locate/negation regressions; the final affected suites passed **135 tests**, including all **14 recovery tests**. Final clarification-copy changes passed the 86-test interpreter/recovery subset. Format, lint, typechecking and builds passed. Independent Standards review had no findings; two Spec findings were fixed and the follow-up review found none remaining. A fresh live browser replay of the sister's exact recommendation request followed by `افتح صفحة القميص الرسمي` completed both tasks and opened `/p/clothing-05`. See `docs/superpowers/plans/2026-09-26-interpretation-recovery.md`.

All three demo services are running. **Ticket 14 remains next.** Preserve the $0.75 total non-resetting key cap, ignored credentials, and unrelated proposal documents/script. No broad architecture refactor or provider change was made.

## Soft preferences and chat redesign — 2026-09-26

The owner confirmed that OpenRouter transcription works on the real device, then prioritized softer recommendation interpretation and chat usability before Ticket 14. Schema 7 / `intent-v17` separates optional subjective preferences from concrete requirements. Vague quality phrases no longer invent mandatory comfort or other product features. Discarding an invented requirement requires positively identified subjective wording; unsupported concrete or mixed phrases remain rejected. Explicit requirements, budgets, cart quantities and guarded authority stay validated. Recommendation explanations use verified catalogue facts, prices, and honest alternatives, with no extra model call. Two bounded live interpretations passed for the owner's exact vague football-shoe request and an explicit comfort request; this is not a claim that every paraphrase will succeed.

The Panel now uses a blue and white Arabic-first layout with independent conversation scrolling, a persistent composer and Stop, clearer suggestion/confirmation cards, and editable starter prompts. Long histories cannot stretch the page or move the Storefront. Mobile keeps both surfaces reachable; short phones allocate extra chat space. New recommendations follow a reader at the bottom without interrupting someone reading older messages. Retry and takeover focus their visible controls. Voice recording disclosure and editable transcription are preserved.

Verification: **148 TypeScript + 402 Python = 550 tests passed**. Repository-wide Prettier, ESLint, Ruff lint/format, Panel typechecking, and all builds passed. The initial full Python run exposed two benchmark expectation mismatches from the new empty optional field; default normalization fixed them, and the final clean 402-test run passed. Actual browser regressions cover long desktop/mobile conversations, recording controls, recommendations followed by completion, and Retry visibility. Independent Standards and Spec review findings were addressed; the focused follow-up found no remaining actionable defect. See `docs/superpowers/plans/2026-09-26-soft-preferences-chat.md`.

**Ticket 14 remains next and is not implemented by this change.** Broad refactors remain deferred. The existing $0.75 non-resetting key cap and local credentials are unchanged. Native select/custom-dropdown interactions are supported, but generic discovery of a hidden cart/account link inside an unfamiliar settings menu is not yet implemented; locate currently requires a visible link.

## Ticket 13 manual-acceptance repairs — 2026-09-26

The owner's `عايز كوتشي للجري` follow-up exposed a model-added `daily_workouts` Catalogue Requirement sourced only from `للجري`. Validation now drops that one unsupported guess while retaining explicitly requested daily workouts and rejecting unanchored daily requirements. Prompt `intent-v16` states the distinction. Three live OpenRouter interpretations of the original follow-up passed; the deterministic safety regressions passed for both `للجري` and the owner's exact `عايز كوتشي جري`. That exact request also completed in a fresh live browser session against the running Agent.

The in-app browser's built-in speech recognition fails with `network` despite microphone permission. When that service fails and the configured key has sufficient non-resetting allowance, the Panel now offers an explicit ten-second WebM recording with an OpenRouter disclosure. The local Agent checks the key's total cap and remaining allowance before sending audio to the pinned transcription model. The transcript fills editable text and is never submitted automatically. The owner authorized raising the same key's non-resetting total cap to **$0.75**; the remote key reports $0.75 with reset `None`, and ignored local `.env` matches. Auto top-up remains off. A synthetic Arabic WebM returned a transcript through both the provider adapter and running Agent HTTP route. The real device microphone and transcript quality still require the owner's manual check in `docs/ticket13-speech-smoke.md`.

Verification: **147 TypeScript + 385 Python = 532 tests passed**, including real-browser cart, safety, recovery, and mobile cases. Build, ESLint, Ruff lint/format, repository-wide Prettier, and diff checks passed. The first browser-suite run accidentally connected to already-running live demo ports and failed on the budget gate. A later mobile test exposed a navigation race in its own setup; it now waits for the sorted Storefront URL. The final clean scripted run passed 385/385. All three demo services returned HTTP 200; the running speech availability route returned `true`, and the local transcription route returned HTTP 200. Ticket 14 remains next.

## Ticket 13 — mobile controls and interaction traps implemented

The Controlled Storefront now has a mobile menu and filter disclosure, a custom mobile sort list, size swatches tied to the canonical select, a live mini-cart summary, and incrementally loaded product cards. Repeated detail links have product group context. The Bridge recognizes disclosure controls, waits for bounded delayed content, rechecks visibility and disabled state before an Action, and exposes form actions only for submit controls. The Panel keeps Stop fixed and reachable on mobile, moves keyboard focus to Shopper questions, and offers Arabic/English browser speech input that fills editable text without sending it. Unsupported speech browsers keep typed input available.

Verification: **521 automated tests passed (144 TypeScript, 377 Python)**, including desktop/mobile browser trap cases and existing cart, recovery, and safety flows. Build, ESLint, Ruff lint/format, repository-wide Prettier, and diff checks passed. Browser screenshots checked the narrow category and filter layouts. No paid model calls were made. A real microphone/permission smoke test remains for the owner; the exact Arabic and English steps are in `docs/ticket13-speech-smoke.md`. Ticket 14 is the next implementation step. The OpenRouter total $0.25 cap remains unchanged. Sol 6 High was sufficient.

## Ticket 12 — refresh recovery resolved

Ticket 12 preserves the pending Shopper question and task identity after refresh. The active Undo toast reloads with only its remaining time and restores the exact prior multi-product cart. Refresh invalidates an unused Confirmation; Retry derives a new one from the current Storefront cart revision. Retry now carries the latest Snapshot so direct cart and filter changes made while paused are authoritative. Overlapping Snapshot messages are reconciled in order. Refresh during navigation or field entry permits fresh-state Retry; an in-flight or unverified Reversible or Guarded Mutation offers Stop and a fresh request, never re-planning the old mutation. Checkout uncertainty tells the Shopper to inspect fictional order history. Tests cover interruption before, during and after each mutation class. No live model calls were needed for this ticket.

Verification: **512 tests passed (138 TypeScript, 374 Python)**, including real-browser Undo refresh and unverified-add recovery. Build, ESLint, Ruff lint/format, changed-file Prettier and diff checks passed. Repository-wide Prettier flags six untouched existing files. Independent Standards and Spec review gaps were fixed. **Ticket 13 — mobile controls and interaction traps** is next. The $0.25 total OpenRouter cap remains unchanged. Sol 6 High was sufficient; Astra was not needed.

## OpenRouter paid evaluation — live cart gate passed

The owner purchased OpenRouter credits and authorized an initial **$0.25 total**
evaluation allowance. The adapter pins google/gemini-2.5-flash, disables thinking,
requires structured-output support, caps provider pricing, checks the remote key's
non-resetting allowance before every paid call and never automatically retries.
The owner corrected the key limit from $100, then daily $0.25, to total $0.25.

**16/16 live intent cases and 4/4 live browser cases passed** with intent-v15 and
schema6. Browser proof covers add, named relative quantity in a mixed cart, one-line
removal and confirmation-bound bulk clear; exact Undo passed for all reversible
edits. Provider-reported spend: **$0.01594408**, remaining key allowance **$0.23405592**.
See `docs/superpowers/plans/2026-09-25-openrouter-cart-evaluation.md` for evidence and
review. This proves the tested batch, not arbitrary language or the complete MVP.

The local demo configuration now selects OpenRouter/Gemini 2.5 Flash. Preserve
the non-resetting $0.25 key cap and all local credentials. The superseded free-Gemini
follow-up is paused. Ticket 12 remains the next ordered product work.

Verification: **496 tests passed (137 TypeScript, 359 Python)**; build, ESLint,
Ruff lint/format and diff checks passed. Standards review's report-directory setup
finding was fixed; Spec review had no findings. Services are healthy and the
owner's cart is restored. No credentials were committed.

## Gemini cart evaluation — adapter ready, live selection gate incomplete

The owner requested Gemini Flash evaluation instead of assuming another Groq fix
proved reliability. A native Gemini adapter now implements the existing LLMClient
interface with JSON Schema, local validation, redacted metadata and cooldown handling.
Gemini 2.5 Flash exposed two actual boundary gaps: bulk `شيل الحاجة اللي فالسلة كلها`
and decrement `بواحد`. Both are fixed with safety regressions. Prompt intent-v15
clarifies cart-only constraints and product-name spans; no validation was bypassed.

Final-prompt live results: selected-item add, named variant add and the owner's
increase request passed (3 of 16 planned). Google then confirmed the project's
**20 requests/day/model free-tier quota** was exhausted; the fourth request was
blocked and 12 were not attempted. Earlier repaired-boundary runs passed set,
decrease, remove and both bulk-clear phrasings with intent-v14. Live Gemini browser
acceptance and repeated final-prompt evaluation remain incomplete. Keep Groq as
the demo provider pending quota reset or owner-enabled billing and renewed evidence.
See `docs/superpowers/plans/2026-09-25-gemini-cart-evaluation.md` for evidence,
review and continuation commands. The local Gemini key is not committed.

Verification: **137 TypeScript + 350 Python tests passed (487 total)**, including
all deterministic browser cases; build, ESLint, Ruff lint/format and diff checks
passed. Standards review had no findings; the Spec matcher finding was fixed.

## Groq cooldown and live acceptance — 2026-09-25

A direct diagnostic identified the actual failure as Groq's token-per-minute limit: limit 8000, used 4299, requested 4690, Retry-After 8 seconds. The daily allowance was not shown exhausted. The adapter now respects the provider cooldown, blocks early retry HTTP calls, avoids automatically repeating invalid structured output, and reports remaining wait seconds. Prompt JSON and schema annotations were compacted without removing validation. Prompt intent-v14 and current-message written-number validation handle the owner's `اتنين كمان` phrase.

Final complete workspace verification: **137 TypeScript and 333 Python tests passed**; build, ESLint, Ruff lint/format and diff checks passed. Bounded Standards and Spec reviews found no remaining actionable issue. Details: `docs/superpowers/plans/2026-09-25-groq-cooldown.md`.

**Live Groq browser acceptance passed:** from a two-product cart, the exact message `عايزك تضيف اتنين كمان من كوتشي صانع اللعب` completed, changing Playmaker quantity from 1 to 3 and leaving Cairo Jacket at 1. The original two cart quantities were restored after this test. All three services are running with the owner's configured provider/key. A minute limit can still occur; the UI now reports its cooldown rather than repeatedly sending the request. No API key replacement, model fallback, architecture refactor or Ticket 12 work was added.

## Manual acceptance fixes — 2026-09-25

Owner testing exposed selected-product handback, Arabic variant validation, relative quantity, and manual empty-cart gaps after Ticket 11B. These are fixed: current visible options resolve the model's missing-query response; explicit Arabic size/color evidence is preserved without using owned-item colors; v6 Structured Intent (`intent-v13`) distinguishes set/increase/decrease and validates direction before changing a named line; the manual clear button now presents a cancelable confirmation and uses existing single-use, revision-bound authority. Ordinary Bridge clicks remain blocked, and stale cart confirmation cannot clear the cart.

Final complete workspace verification: **137 TypeScript and 330 Python tests passed**, including all seven cart browser cases and existing Ticket 09/10 safety cases. Build, ESLint, Ruff lint/format, changed-file Prettier and diff checks passed. Initial stale prompt-version assertions were updated before the final clean run. The independent Standards/Spec review findings were repaired and rechecked; see `docs/superpowers/plans/2026-09-25-manual-cart-repair.md`.

The Agent was restarted to load the owner's updated key. All three manual services are healthy, and the owner's two saved cart lines were restored after isolated tests. Live Groq responses reproduced the original missing-query and dropped-variant gaps; deterministic regressions verify their fixes. No claim of a complete live-provider browser run is made. Ticket 12 remains next; architecture refactors remain deferred.

## Current frontier: Tickets 11 and 11B resolved (2026-09-25)

The owner deferred architecture-report refactors and prioritized the visible graduation MVP. Implemented available-product add with selected size/color, quantity changes, individual removal (including the last line), optimistic feedback with rollback, and exact ten-second Undo. Consecutive same-line quantity edits retain the original pre-burst state and deadline. Stale/duplicate edits are rejected and ordinary edits invalidate older guarded authority. The Agent uses current visible controls, rejects unsourced variant overrides, and reports success only after Storefront confirmation; uncertain mutations are never automatically repeated. Structured Intent request/schema is now v5 (`intent-v12`).

Ticket 11B adds an Arabic-first RTL retail presentation across home, category, product, cart and simulated checkout, with native local illustrations, responsive layouts, explicit fictional-payment boundaries, keyboard focus and reduced-motion support. Existing Bridge safety and guarded-checkout regressions remain green. Visual checks covered all five pages at 1280px and 390px; screenshots are local ignored artifacts under `eval/reports/ticket11b/`.

Final full-workspace `pnpm test`: **137 TypeScript tests and 317 Python tests passed**. Build, ESLint, Ruff lint/format, changed-file Prettier and diff checks passed. The initial full run identified an old schema-v4 assertion; after updating it, a fresh entire-workspace run passed. One existing third-party multipart deprecation warning remains. Standards review found two defects and Spec review found three; all were repaired and regression-checked. Details: `docs/superpowers/plans/2026-09-25-cart-review.md`. Browser tests use the scripted provider; no new live-provider reliability claim is made.

The owner explicitly authorized one clean working-MVP commit including the earlier uncommitted ticket code. Unrelated proposal/template artifacts remain outside that commit. **Ticket 12 — Recover Mutation state across refresh** is next. The Storefront remains local, in-memory and fictional; no architecture refactor, generalisation or AWS work was added.

## Historical checkpoints

## Architecture review follow-up: Tickets 09 and 10 hardened; Ticket 11 still next

The owner requested a current-codebase architecture review focused on Tickets 09 and 10, with fixes for verified findings. The review reproduced three groups of Bridge safety gaps and repaired them without changing the Agent wire contract or implementing Ticket 11:

- Origin enforcement now uses browser-resolved link/form destinations, native form ownership, and submitter overrides, including clicks on button descendants. Invalid destinations fail closed.
- Sensitive Field protection now recognizes autocomplete token lists and password tokens, blocks sensitive select Actions (including dynamically changed fields), and excludes textarea/select contents from aggregate and referenced Snapshot names. Sensitive option text cannot leak via another element's `aria-labelledby`; ordinary option names remain available.
- Guarded-form classification now handles absolute URLs, associated forms, submitter overrides, and the route case/trailing-slash variants accepted by the Controlled Storefront. These ordinary-click paths are blocked at the Bridge. The Storefront's independent token check already rejected unauthorized submissions; no full-stack unauthorized order was demonstrated.

Fresh final verification: **307 Python tests and 131 TypeScript tests passed**, including all twelve Ticket 09/10 browser tests. Seventeen direct regressions were added in `bridge/tests/safety-review.test.ts`, plus three browser regressions in the existing Ticket 09/10 evaluation files. Production build, ESLint, Ruff lint/format, changed-file Prettier, and diff checks passed. A review iteration caught a TypeScript narrowing error that prevented browser startup; it was corrected before the successful final full-suite run. A second reviewer reproduced two residual cases, verified their repairs, and found no additional actionable issue in the focused changes. Tests used the scripted provider; no new live-provider reliability claim is made.

The requested visual report is local-only at `C:/Users/pc/AppData/Local/Temp/architecture-review-20260925-1026.html`. Its follow-up candidates are: deepen Bridge Action-target interpretation (strong; immediate bugs fixed), keep guarded authority and the cart state transition together inside the existing Storefront module (strong), and concentrate the Agent Confirmation lifecycle (worth exploring). These remain incremental architecture recommendations, not prerequisite rewrites or a change to the implementation frontier. The substantial pre-existing dirty checkout was preserved; no commit or deployment was made.

## Current frontier: Ticket 10 resolved; Ticket 11 next

The owner selected Sol/high for the safety-sensitive Ticket **10 — Confirm Guarded Mutations exactly**, now resolved for the local Controlled Storefront. Explicit bulk cart clearing and fictional checkout submission produce a localized, distinct confirmation card. The exact card answer is bound to the current task, Guarded Action type, stable form target, cart revision, and intended effect. It expires after sixty seconds, relevant cart state change, or refresh; generic, unrelated, negated, stale, and duplicate authority is rejected. Opening cart or checkout remains ordinary navigation. The Bridge blocks an ordinary click or submit-through-typing on a guarded form, rechecks the current target and form validity, and does not read fictional card fields. The Storefront consumes one matching token and verifies the revision before changing its in-memory cart or recording a fictional order. The Agent verifies the resulting page before reporting success and never automatically replays an uncertain mutation.

Ticket 10 adds only a test-seeded cart and simulated checkout so its safety flow can be exercised. Normal product add, quantity changes, one-line remove, ten-second Undo, and richer cart persistence remain Ticket **11**; the polished Egyptian retail UI remains **11B**, after Ticket 11. The test-only seed and local registration endpoint are not production commerce/payment authorization against another process on the same machine. Development listeners now bind to loopback. The owner can test the guarded browser path with the scripted provider without consuming Groq quota; the live Groq baseline recognized English and Egyptian Arabic clear-cart requests in two probes, then returned HTTP 429 on the next probe. Do not conflate this with a live-provider reliability pass.

Fresh verification on 2026-09-25: **304 Python tests**, including five Ticket 10 browser scenarios, and **114 TypeScript tests** passed; production build, ESLint, Ruff lint/format, changed-code Prettier, and `git diff --check` passed. A standalone test also caught and closed a circular-import bug that the broader import order had masked. The next ordered work is Ticket 11, not AWS, independent-Storefront generalisation, catalogue expansion, or UI polish alone. All lower sections are dated historical checkpoints and may name an older frontier.

## Current frontier: Ticket 09 safety gate complete

Ticket **09 — Enforce the core safety boundary** is resolved for the Controlled Storefront local MVP. The Bridge pins the Storefront origin and checks explicit navigation, clicked links, and submitted forms before acting; it also rechecks field sensitivity at execution time. Sensitive Field Snapshot metadata is generic, including textareas, so input values cannot be echoed through their accessible names. The v1 Action contract has no `read` Action. Disabled purchase controls return blocked rather than a false success. The Storefront's `/cart/items` boundary rejects unavailable products with HTTP 409; available products still return HTTP 501 because Ticket 11 owns actual cart additions, options, and Undo. This is not a claim that cart additions work yet.

Ticket 09 deterministic and browser checks include off-origin Actions, sensitive checkout values, unavailable products, and visible, hidden, delayed, and accessibility-label instructions embedded in Storefront content. The Intent Interpreter receives the Shopper's request and trusted Storefront Definition, not raw page text. Full verification on final code is recorded below; scripted browser evaluation is used so Groq free-tier throttling does not confound the safety result. The next ordered ticket is **10 — Confirm Guarded Mutations exactly**.

Final verification: **281 Python tests** and **104 TypeScript tests** passed, including four Ticket 09 browser tests; production build, TypeScript ESLint, Python Ruff lint/format, changed-file Prettier, and `git diff --check` passed. The manual-demo services were restored and returned HTTP 200 on Storefront 4000, Agent 8000, and Panel 4100; a live local request to add an unavailable item returned HTTP 409. No live Groq accuracy claim is made from the scripted safety suite.

The owner also approved a separate **11B — Polish the Controlled Storefront UI** ticket, blocked by Ticket 11. It covers a modern Arabic-first Egyptian retail presentation while preserving all Agent-facing `data-testid`, accessibility, route, and semantic selectors. Visual polish is not bundled into the Ticket 09 safety change and does not start before cart behavior is established.

## Current manual feedback: named product-page follow-up

The owner showed a recommended `ممشى النيل` shoe followed by `طب ينفع توريني صفحة كوتشي ممشى النيل ده`; the prior Agent turned that into a literal category search and claimed no match. This was a product handoff gap, not only weak Storefront search. The Controlled Storefront now serves a read-only individual product page at `/p/{product_id}` (404 for unknown IDs), with the route declared in the Storefront Definition and category cards linking to it. The Agent carries only the previous verified suggestion IDs/names into the next turn; Structured Intent v3 can select `open_product`, then the Intent Boundary and Session Store require an exact prior suggested ID and a current Shopper source. A named page request also recovers safely when the model mistakenly emits a browse/search intent. Unnamed references among several suggestions ask which product; a model-invented ID cannot navigate. New hard requirements are not silently discarded for this recovery.

The exact two-turn scripted regression was red before the repair (no product Action; `/p/shoe-09` was 404) and green after it, including the misclassified-search variant. Agent tests, Storefront tests, and a headless Chromium product-page check passed; the three demo services returned 200 after Store/Agent restart. The first opt-in live Groq probe returned HTTP 429 twice on the exhausted key. After the owner rotated the key, `python -m eval.product_followup_probe` returned `open_product` for `shoe-09`; the Agent service was restarted to load the new key. The subsequent live browser check `python -m eval.product_followup_browser` passed both turns: `رشحلي كوتشي كاجوال بيج مقاس 43` produced a verified `shoe-09` recommendation, and the owner's unchanged `طب ينفع توريني صفحة كوتشي ممشى النيل ده` opened the exact product page rather than a search. An initial browser setup prompt naming the product directly produced ordinary browse results, not a recommendation, so it was not counted as a follow-up result. The isolated browser-suite runner was not completed while the owner's demo services occupied its fixed ports. Ticket 09 remains the next ordered plan ticket; this is a bounded 07E follow-up repair, not a retrieval/database or AWS milestone.

## Current frontier

The owner-prioritized 07E/08 semantic debugging batch is complete (2026-09-24), with Ticket 09 still the next ordered ticket. Structured Intent v3 distinguishes browse/recommend/style, separates multiple owned pieces from requested-product constraints, and retains bounded clarification context before catalogue routing. Explicit revisions can remove or replace prior requirements or switch back to browsing. Semantic navigation no longer requires every phrase to match a verb dictionary; a single previous verified destination supports natural followups. Canonical/source validation and deterministic catalogue, currency, login, origin, confirmation, lease, Stop and stale-action boundaries remain enforced. The generic style evaluator replaces the black-trousers special case and shows up to three verified options with readable Arabic reasons; alternatives retain named gaps.

Final verification: **272 Python tests** (including all six scripted browser regressions) and **93 TypeScript tests** passed; build, ESLint, Ruff lint/format, changed-document formatting and diff checks passed. All seven live Groq acceptance cases passed in `eval/reports/semantic-repair-browser-20260924T194201Z.json`: both outfit requests, novel account wording, original black-trousers styling, and all three unchanged owner requests. After the final review fixes, the owner's outfit passed again on final code in `eval/reports/semantic-repair-browser-20260924T195450Z.json`. The live locate-orders → natural open followup → non-looping sign-in wait → shopper authentication → completion flow passed in `eval/reports/semantic-followup-browser-20260924T195250Z.json`. An earlier deictic-followup run failed; the prompt now explicitly exposes the prior verified destination and the failed report remains historical evidence. Review fixes covered correction-span masking, owned-context replacement, overbroad/overlapping source spans, and unknown-colour explanations. This is evidence for the repaired batch, not a claim that arbitrary natural language or the whole project is bug-free. No .env, provider, seed-data, database or AWS change was required. Demo services were restarted for manual testing; refresh the Panel once after the Agent restart. Routine next-ticket implementation can return to the owner's cheaper-model workflow; Astra is not required to continue this completed repair.

Ticket 08 post-acceptance sign-in/interpretation repair is implemented and verified on 2026-09-24. The shared Intent Boundary now recognizes unambiguous Egyptian `تفتحلي`-style open requests while preserving clarification for mixed locate/open cues. On an unchanged expected sign-in page, `Continue` no longer creates another handoff Action, narration, or task step: the Panel keeps the original question, explains that the Shopper must sign in directly, disables repeated Continue until the Storefront page changes, and keeps Stop available. A fresh authenticated orders Snapshot still allows the existing newest-order Spotlight, with no credential read/entry or automatic authentication. Interpretation pauses now distinguish provider request limits, timeouts, network/HTTP failures, invalid model output, unavailable catalogue facts, interruption, and unknown errors using fixed redacted messages; the last reason survives refresh. A scripted end-to-end browser regression covers pressing Continue before sign-in and then signing in to reach the newest-order Spotlight. The isolated full suite passed **236 Python** and **93 TypeScript** tests; build, Ruff lint/format, ESLint, changed-file Prettier, and diff checks passed. The manual-demo services were restored and returned HTTP 200 on ports 4000, 8000, and 4100. The exact intermittent cause of the owner's earlier Retry screenshots remains unobserved; the new messages make future failures diagnosable without claiming all were throttling. Ticket 09 remains next; no catalogue, checkout, or AWS work was started.

Ticket 08 post-acceptance browser feedback is addressed in the local working tree. A Spotlight now gives the targeted Storefront element a visible high-contrast outline and halo, and scrolls it toward the viewport center smoothly (immediately when reduced motion is requested). An immediately following `افتحهالي` can use only the prior verified cart Spotlight target; this single-use destination is cleared for other requests and is never a full conversation transcript. The Panel now registers `ask_shopper` with the Bridge ledger while keeping its no-op Action Result out of the Agent's answer path, so a clarification choice's next Action has the expected sequence without relaxing duplicate/stale Action rejection. The exact ambiguous-choice browser regression and Spotlight visibility check pass. The complete isolated Python suite passed **229 tests**, the TypeScript suite passed **91 tests**, and build, Ruff, ESLint, changed-file Prettier, and diff checks passed. A scripted regression also ensures the Arabic follow-up keeps Arabic narration. A first live Groq follow-up run reached `/cart` after the verified Spotlight, but its final diagnostic print hit a Windows console encoding error; the immediate repeat paused during intent interpretation, consistent with the documented free-tier reliability caveat. The three demo services were restored and returned HTTP 200 on ports 4000, 8000, and 4100. Ticket 09 remains the next ordered ticket; no new catalogue, AWS, or checkout implementation was started.

Ticket **08 — Locate cart and order-history destinations** is resolved for the Controlled Storefront local MVP on 2026-09-24. The Intent Boundary and scripted planner now share four Storefront-backed destination aliases. Deterministic validation repairs a dropped model destination or locate/open mode only when the Shopper's words are unambiguous; conflicting destinations or actions ask a trusted question without a browser Action. Model-only navigation, prompt override, invented product Constraints, and mixed product/navigation requests cannot silently redirect the task. Prompt `intent-v8` adds English, Arabic, and Franco-Arabic navigation examples. The existing controlled routes, safe demo sign-in handoff, newest-order Spotlight, and Sensitive Field protections remain in place.

All seven Ticket 08 scripted browser Evaluation Cases passed on the final code. All seven live Groq browser cases also passed individually on 2026-09-24: cart/order-history locate Spotlights, explicit cart/account/checkout navigation, logged-out order-history handoff, and authenticated newest-order Spotlight (two Actions). The final-code checkout browser check had one transient Retry/90-second timeout with zero Actions, followed by a direct Groq `navigate → checkout` result and a passing one-Action browser rerun. This is a local free-tier reliability caveat, not evidence that the failed attempt succeeded. The final non-browser run passed 219 Python tests and 88 TypeScript tests; the isolated scripted Ticket 08 browser test, Python Ruff check/format, TypeScript ESLint, production build, and `git diff --check` passed. The `pnpm lint` shortcut still selects system Python without Ruff, so equivalent checks used the project virtual environment. Services are restored on ports 4000, 8000, and 4100 for manual testing. The next ordered ticket is **09 — Enforce the core safety boundary**; no AWS, database, or catalogue expansion was made for Ticket 08.

Ticket **07E — Integrate real intent into Shopping Tasks** is resolved for the approved Stage 1 Controlled Storefront scope. The three unchanged owner-written browser requests passed on 2026-09-23 with Groq `openai/gpt-oss-120b`, prompt `intent-v7`, Structured Intent schema 2, and a versioned read-only catalogue. An additional open-ended black-trousers styling request also passed in the real browser. Ticket 08 now provides navigable cart and checkout preview pages, but cart mutations, payment, and order submission remain Stage 2 work and must not be described as working yet. Tickets 07A through 07E remain uncommitted local work.

Post-acceptance manual feedback exposed a missing football-shoe type mapping. The Storefront had a working `football` filter, but its authoritative Definition did not allow that type, so the Agent silently broadened an Egyptian Arabic football-shoe request to size-only shoes. The Definition now includes football terms; direct Intent Boundary tests show a dropped football type requires clarification and a valid football type yields `/c/shoes?type=football&size=43`. A live Groq browser run of the exact Shopper phrase `عايز كوتشي كرة اكسر بيه الدنيا مقاسي 43` passed in one navigation, showing four filtered products. For Ticket 08, the owner requested an orchestrator-and-cheaper-implementer split instead of relying on Terra; Luna agents implemented bounded slices with primary-agent review.

The first run of the three owner requests exposed an acceptance failure: use-case, material, style, and nonnumeric price preferences were not grounded. Stage 1 now resolves that failure with explicit fixture facts and deterministic verification. The original failure is retained below as historical evidence, not the current result. The rule remains: never broaden a search silently or call an unverified product an Exact Match.

The approved design is `docs/superpowers/specs/2026-09-23-grounded-catalogue-discovery-design.md`; the execution plan is `docs/superpowers/plans/2026-09-23-grounded-catalogue-discovery.md`. The existing product source remains `store/src/catalogue.ts`, despite older plan wording about JSON fixtures. The Storefront publishes public facts at `/__catalogue/v1/products`; there is no database, vector store, or Agent-side copy of the catalogue.

The owner has since selected **fashion and shoes** as the graduation-project focus and approved a controlled Storefront with curated products, simulated EGP prices/stock, and safe simulated checkout—not a live external retailer. The owner reaffirmed grounded attributes, no invented product facts, payment outside the Copilot, explicit checkout confirmation, and finishing the current safety/browser baseline before larger-catalogue retrieval or AWS deployment. Research into datasets, multilingual retrieval, and cost-conscious AWS options is recorded in `docs/research/2026-09-23-aws-shopping-copilot-options.md`. The 60-product catalogue remains useful as a deterministic safety fixture, not necessarily the final demonstration catalogue. No larger-catalogue, retrieval, checkout, or AWS implementation has been approved through a detailed design/plan yet.

## Established decisions

- Groq `openai/gpt-oss-120b` with low reasoning effort is the pinned local MVP baseline after NVIDIA candidates failed the evidence gate.
- The local baseline is an explicit development decision, not a claim that GPT-OSS passed the strict 95%/100% selection gate. Strict re-benchmarking is deferred to the final Amazon Bedrock migration.
- Model output is limited to a validated Structured Intent. Deterministic code retains Money, Storefront-vocabulary, clarification, navigation, and Action-safety authority.
- The local Storefront currency is injected from its definition and remains EGP-only.
- Ordinary tests use the explicit scripted provider and never contact a real provider.
- Full prompts and responses are not recorded by default. The adapter records redacted call metadata only.

## Verified evidence

- Latest 07E owner-request browser report: `eval/reports/owner-07e-browser-20260923T200300Z.json` (ignored local report, UTC). All three unchanged requests passed after the compositional road-running vocabulary refinement. Summer/beach/light/comfortable shirt: `clothing-04`, Exact Match at 650 EGP. Franco wedding/black/leather/lower-price request: zero Exact Matches; `shoe-07` and `shoe-08` are labelled Alternatives with respectively unverified formal suitability and unavailable black colour, ordered by EGP price. Daily-workout/street-running size-43 request: `shoe-02` and `shoe-04`, Exact Matches at 1750 and 2450 EGP. Each result was visible in the Panel, with no browser Action or cart mutation.
- Additional real-browser styling report: `eval/reports/owner-07e-browser-20260923T155454Z.json` (ignored local report, UTC). Owned black trousers produced three available upper-body Styling Suggestions (`clothing-06`, `clothing-04`, `clothing-05`) with short compatibility reasons and no cart mutation.
- The earlier unpaced browser runs saw Groq HTTP 429 under its free-tier token window. The three-request acceptance runner spaces calls by 45 seconds so semantic accuracy is not confused with rate limiting. This is a development throughput limitation, not a strict model-selection pass or a production reliability claim. The live Agent still pauses with visible Retry and Stop if the provider throttles it.
- Latest regression verification on 2026-09-23: 167 Python tests and 75 TypeScript tests passed; production build, Python Ruff lint, TypeScript ESLint, focused formatting, and `git diff --check` passed. The new football tests were observed failing before the vocabulary fix and passing after it. A direct test also rejects inferring road-running suitability from "street" alone. Direct tests cover the read-only catalogue contract, exact/alternative/styling evaluation, multilingual zero-silent-drop recovery, provider failures, Stop/stale results, refresh restoration, and Action safety. The original three-request browser run used prompt `intent-v7` and Structured Intent schema 2. Repository-wide Prettier still flags four older files noted below; changed code files pass formatting.
- Manual Stage 1 test services were restarted after isolated football browser verification and returned HTTP 200 at `http://localhost:4000/`, `http://127.0.0.1:8000/health`, `http://localhost:4100/`, and the read-only catalogue route. They are background local processes, not persistent deployment.

- The NVIDIA endpoint and account work with current models; several previously approved model IDs were retired by NVIDIA during this work.
- Current live benchmark candidates are:
  - `nvidia/nemotron-3.5-lightning-30b-a3b`
  - `nvidia/nemotron-3-super-120b-a12b`
  - `nvidia/nemotron-3-ultra-550b-a55b`
- The full prompt, with reasoning disabled, returned a valid Arabic/mixed Structured Intent from the Super and Ultra candidates. Lightning was schema-valid in its pilot but invented constraints, so the corpus gate must decide it rather than the smoke result.
- The v1 benchmark report is `eval/reports/intent-benchmark-20260917T185654Z.json` (local, ignored output): no candidate passed the selection gate.
- The v2 benchmark report is `eval/reports/intent-benchmark-20260918T021838Z.json` (local, ignored output): no candidate passed the selection gate.
  - Super improved from 30 to 37/104 exact runs and from 11 to 20/66 critical-safety passes; P95 5,609 ms.
  - Ultra improved from 40 to 42/104 exact runs and from 19 to 23/66 critical-safety passes; P95 22,687 ms.
  - The remaining evidence gaps are Franco-Arabic and mixed-language accuracy, unsupported or malformed budgets, and some off-topic/adversarial outcomes.
- The v3 benchmark report is `eval/reports/intent-benchmark-20260918T023532Z.json` (local, ignored output): no candidate passed the selection gate.
  - The deterministic foreign-currency and malformed-budget checks improved Super to 55/104 exact runs and 33/66 critical-safety passes. Its P95 was 6,546 ms.
  - Ultra remained unsuitable: 42/104 exact runs and 12/66 critical-safety passes, with a 17,342 ms P95.
  - The implementation gap is now explicit: the pre-check runs after provider structured-response validation, so an invalid model response can prevent deterministic budget clarification from being returned. The next change moves that safe fallback ahead of the provider boundary and adds diagnostics for validation failures.
- The v4 benchmark report is `eval/reports/intent-benchmark-20260918T024547Z.json` (local, ignored output): no candidate passed the selection gate.
  - The Intent Boundary now returns a deterministic EGP clarification, and blocks browser action, when a foreign or malformed budget message has invalid model output. This behavior has a direct regression test.
  - Super is the only partially viable candidate, but it reached only 54/104 exact runs and 31/66 exact critical-safety runs, with six `HTTPStatusError` failures. Its P95 was 6,358 ms.
- Ultra is unavailable for this workload: 93/104 runs failed with `HTTPStatusError`, leaving 10/104 exact runs. Its reported low latency is therefore not meaningful.
  - Reports now contain only redacted failure categories; no shopper text, model response, or credential is captured.
- NVIDIA viability probe after the v4 run: `meta/llama-3.3-70b-instruct` is retired from the live catalog. The two currently listed 70B alternatives, `nvidia/llama-3.1-nemotron-70b-instruct` and `nvidia/llama3-chatqa-1.5-70b`, both returned HTTP 404 from NVIDIA's chat-completions endpoint during a no-action connection test. They were not benchmarked or pinned.
- The Groq adapter is implemented locally. It uses non-streaming strict JSON Schema output, configurable reasoning effort, and preserves the existing provider-neutral `LLMClient` seam.
- The architecture review confirmed that Intent Interpreter and browser code remain provider-independent. It removed NVIDIA-specific switches from the benchmark runner and separated critical-safety scoring from full semantic exactness.
- Prompt v5 resolves the strict-schema optional-field conflict by requiring null for absent optional fields. Model-authored clarification copy was removed from Structured Intent; trusted application code remains the only source of clarification wording.
- Groq `qwen/qwen3.8-27b` passed the mixed-language smoke and a nine-category viability sample with 9/9 schema and safety results, but only 7/9 exact. Repeated samples showed invented unstated Constraints including minimum price, availability, and cart target. It is rejected without a full benchmark.
- Groq `openai/gpt-oss-120b` passed the smoke. Its first nine-category sample was 9/9 schema, 9/9 safety, and 8/9 exact; eighteen additional unseen cases were 18/18 schema, 17/18 safety, and 12/18 exact. It followed an Arabic injected checkout instruction and therefore did not pass the strict selection gate.
- Structured Intent now rejects any result that mixes navigation authority with product-discovery Constraints. A live replay of the unsafe Groq case is rejected before action planning.
- The Intent Boundary also detects the approved Arabic/English prompt-override pattern deterministically and refuses navigation authority even when a model returns a pure navigation result.
- By explicit owner decision, the ignored local `.env` pins Groq `openai/gpt-oss-120b` with low reasoning effort for local development. The API key remains local and ignored.
- Ticket 07D is resolved under the documented local-development waiver. Ticket 07E may proceed; the strict model gate remains intact for the final Bedrock migration.
- Ticket 07E connects the existing `SessionStore` to validated Structured Intent; the scripted provider remains the ordinary network-free test path. Provider errors pause a task with Retry and Stop. Stop and refresh invalidate a pending model-call identity so late output cannot issue an Action.
- The Panel displays interpretation status and Retry; an in-flight submission or active task is not unlocked by an unrelated Storefront Snapshot.
- Prompt `intent-v6` carries forward validated clarification context. The opt-in Groq browser smoke passed the mixed-language case in one Action; ignored report `eval/reports/real-browser-smoke-20260922T213445Z.json` records provider, model, reasoning effort, prompt/schema versions, and browser outcome.
- Automated verification on 2026-09-23: 147 Python tests and 71 TypeScript tests passed; Python and changed TypeScript lint/format checks, production build, and `git diff --check` passed. The remaining 07E acceptance gate is the three unseen owner-written browser requests.
- Manual 07E testing uses three running local services: `corepack pnpm run store` (4000), `.venv\Scripts\python.exe -m uvicorn agent.app:app --host 127.0.0.1 --port 8000` (8000), and `corepack pnpm panel` (4100). Use `pnpm run store`, because `pnpm store` invokes pnpm's package-store command instead of this project's development script. These services were started and all three URLs responded on 2026-09-23; their running state is temporary.
- A restarted Agent loses its in-memory session while the Panel may retain the old session ID in browser storage. The Agent returns 404 for that ID; the Panel previously recovered only from 410 and stayed on "Reconnecting...". The Panel now clears the stale session, starts a fresh one on either 404 or 410, and explains the reset in the conversation. The open browser page was observed ready with its input enabled on 2026-09-23. Panel tests (18), targeted lint/format, Panel build, and `git diff --check` passed. This does not add Agent-session persistence across restarts or replay an uncertain Action.
- The 07E discovery boundary now preserves recognized category, type, color, size, maximum budget, sort, and explicit use-case wording instead of silently broadening a search when the model omits them. Missing or mismatched details require clarification before browser action. The Storefront vocabulary now recognizes `قميص`/`قمصان` as shirts and `بني`/`بنى` as brown; product seed data was not changed. Unsupported hiking/grip suitability cannot yet be verified from the fixture metadata, so the Agent asks for clarification rather than claiming a suitable product or a catalogue-wide absence.
- A successful discovery Action Result is not reported as a matching-product success unless the visible Storefront result-count heading is present. Zero products produce an explicit no-match summary; a missing count produces an unverified-results summary. Focused tests cover dropped Egyptian/mixed details, zero results, and an absent count. Real-model browser checks passed for the mixed-language filter, an empty filtered result, and the owner's `طب عايز قميص لونه بني` request: one Action to `/c/clothing?type=shirts&color=brown`, zero products, and `لا توجد منتجات مطابقة لطلبك.`
- Verification for this boundary pass: `corepack pnpm test` passed (73 TypeScript and 156 Python tests); TypeScript ESLint, Python Ruff lint/format, production build, targeted Prettier check, and `git diff --check` passed. The repository-wide Prettier check still flags four pre-existing/unrelated unformatted files: `.scratch/shopping-template/template-style-evidence.json`, `eval/intent-corpus.json`, `IMPLEMENTATION_PLAN_FINAL (1).md`, and `MVP_PLAN.md`. The development services were restored on ports 4000, 8000, and 4100 after isolated browser tests.
- First browser run of the three previously unseen owner requests (2026-09-23): the Egyptian Arabic beach/summer shirt request navigated to clothing with `type=shirts` and a literal summer/light-shirt query, then honestly reported zero products, but offered no grounded alternative. The Franco-Arabic wedding/formal/black/leather/affordable shoes request navigated to `/c/shoes?color=black` and incorrectly declared matching products despite dropping formal, leather, and the price preference. The mixed Arabic/English daily-workout/street-running shoe request asked for a generic clarification without taking an Action; it did not invent a match. This is concrete evidence that the 07E owner-request gate is **not passed**. Do not add those exact phrases to a keyword list or count broad black shoes as a success.
- A repeated live run of three earlier known browser cases had mixed outcomes: the mixed-language filter and empty-result checks passed in the first two rounds; the Franco-Arabic case timed out in the evaluator despite completing a browser Action because its real-model completion status was Arabic while the scripted case expected English. The third round also saw model/action timeouts. The real-model evaluation needs a language-independent completion assertion and investigation of intermittent model latency, separate from the semantic failure above. Earlier isolated deterministic test results remain valid but do not establish live stability.

## Continuation rules

- Update this file when a ticket resolves, a benchmark result is produced, a provider/model decision changes, or a manual test becomes available.
- Keep credentials only in ignored local `.env`; never copy them into code, fixtures, reports, or documentation.
- Continue with the first unresolved ticket whose blockers are resolved. Use the local issue tracker under `.scratch/shopping-copilot-local-mvp/` as the detailed source of truth.
- Do not weaken the deferred selection gate or modify the ignored local `.env` without an explicit decision.
