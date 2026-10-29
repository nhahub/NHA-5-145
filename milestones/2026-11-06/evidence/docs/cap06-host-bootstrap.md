# CAP-06 explicit host startup API

23October continuation: an explicit inactive CLI and separate Agent-only unit are
now prepared; see [host launcher](cap06-host-launcher.md). The22October description
below records the factory's original preparation. No service has been activated.

22 October 2026. Restricted settings and owned host-resource assembly are prepared
and tested locally. No host service, environment selector, systemd command, cloud
backend or qualified provider was activated. This is not deployment acceptance.

`load_host_settings(config_path)` reads exact version1 JSON with these fields:

| Field                                       | Meaning                                                                                                             |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| version                                     | Integer1                                                                                                            |
| release / fingerprint                       | Absolute selected release and independently pinned release.json SHA256                                              |
| catalogue                                   | Existing external catalogue SQLite file                                                                             |
| table / namespace                           | Fixed remote authority binding                                                                                      |
| invitation_identity / lifecycle_identity    | Existing canonical authority UUIDs                                                                                  |
| service_secret_file / readiness_secret_file | Separate external raw secret/key files                                                                              |
| inference                                   | Exact existing inference.config.REQUIRED string mapping, including ledger path/identity/prices/queue/storage bounds |
| admission_limits                            | Exact existing AdmissionPolicy limit names and strict integer values                                                |

No extra/duplicate fields, interpolation, inline key, AWS credential or provider
override is accepted. JSON is bounded to16384bytes; service secret to32–128ASCII
non-whitespace bytes and readiness key to32–64raw bytes. Settings copy/freeze maps,
hide secrets in repr, validate exact production release/origins and existing
allowance using current price/queue validators. They never initialize, enable,
reserve, settle, restore or reset allowance. Paths are distinct existing files
outside the release; direct HostSettings construction also validates semantics.

The default private reader requires POSIX. It checks file type, owner root/current
effective UID, owner-read, no group/other permissions and one hardlink. Parent
directories must be root/current-owned, nonsymlink directories with no group/other
write permission. It uses no-follow/nonblocking open, bounded read and stable
fstat metadata before/after. Errors disclose only generic refusal. No production
secret was generated, read or provisioned here. Windows refuses default loading;
tests use a trusted reader seam plus metadata tests. Real Linux ownership, parent
paths and permissions must still be verified on the eventual host.

## Assembly and lifetime

`create_host_app(settings, *, sdk_factory, provider_ready, model_client,
http_transport, clock)` is an explicit Python API invoked before an event loop
starts. Omitted optional arguments use the existing fixed Stockholm SDK builder,
explicitly false unqualified-provider verifier, lazy configured Bedrock client,
ordinary HTTP transport and wall clock. No client is made by importing the module.
Execution root must match the canonical selected release before SDK construction;
another checkout cannot name a verified artifact and claim to be that artifact.
Start the eventual host interpreter with `-B` (as in the existing service unit);
the artifact verifier intentionally rejects generated executable bytecode caches.
Synthetic tests patch the private root observation and do not claim packaged
execution. The fresh artifact includes both bootstrap and configuration modules.

Assembly reads existing DynamoDB authority, creates one owned async admission and
work adapter, explicit StorefrontService/lexical CatalogueClient, and the normal
single GuardedClient. No double wrapping/reservation. It installs HostChecks and
signed HostReadiness. Exact app.scpilot.tech/store.scpilot.tech and fixed private
loopback origins are derived from settings. StorefrontService disables environment
proxies on async identity and synchronous Confirmation requests.

The app factory accepts a copied `environment` mapping throughout provider,
allowance/admission/lifecycle, identity/service mode, test routes, retrieval and
encoder selection. Explicit mode never loads dotenv/local identity or ambient
ranking/cache flags, and never mutates os.environ. Legacy behavior remains when
omitted, with its environment snapshot taken after settings/dotenv loading. The
legacy `agent.app:app` attribute is now created and cached lazily; import alone
does not construct an unrelated default app or touch local provider configuration.

Qualification is checked outside the lease actor lock before work admission and
model entry/output. A shared verifier has one retained task and a1second response
bound; slow cancellation cleanup keeps that slot, so requests cannot accumulate
verifiers. Pending leases continue renewing while verification is unresolved.
Normal actor authority checks and final generation/failed/closed fences follow
the callback. Stop ownership stays available even when qualification is false.

Current `unqualified_provider` always returns false. Even stale persisted
healthy=true cannot authorize requests, invoke the model or consume inference
allowance. No new qualification flag/report format or OpenRouter fallback exists.
CAP-05 remains blocked by zero applied quotas; current diagnostics and held charges
are unchanged. Injecting a successful test double is not qualification evidence.

Lifespan initializes one generation before serving and drains health, concrete
checks, provider gate/work, admission pool/shared SDK, then service. A retained
closing task also drains lifecycle workers before the SDK, even if the earlier
close await is cancelled. The SDK is closed off-loop once after its users drain.
Startup/factory failure closes constructed
resources and returns generic refusal without original error context. Caller must
run the returned app's lifespan; assembling an object alone is not service startup.
No autoreplay or pending-state reconstruction was added.

## Remaining deployment work

The current launcher/systemd unit still uses the prior runtime path; selecting
this API for a real host remains an approved deployment operation. Real POSIX
permission/key provisioning and packaged execution, Linux Lambda dependencies,
reliable external observation delivery, effective IAM/OAC/event/account eligibility,
final resource/cost/rollback approval and deployed desktop/Android acceptance stay
open. Free plan, Stockholm and zero cash persist. No scheduler service was added.

See [concrete checks](cap06-host-checks.md),
[design](superpowers/specs/2026-10-22-cap06-host-bootstrap.md) and
[plan](superpowers/plans/2026-10-22-cap06-host-bootstrap.md).
