# Explicit captured provider qualification

24October2026. Implementation/testing only; actual key custody, host acceptance
and deployment are not approved or established by this document.

The owner approved binding the retained OpenRouter model acceptance to the
executing release/configuration and protected custody. The owner's simplifying
amendment is authoritative: read and hash protected evidence once at startup,
with no runtime file-reading worker or per-request disk hashing. The20source
hashes remain an [offline audit](cap06-openrouter-reconciliation.md) concern.
A reviewed source bugfix follows normal release verification and explicit
rebinding; it does not require editing a runtime source-pin table.

## Explicit startup

HostSettings v1/v2 stay unchanged. With neither new option, the Agent retains its
default provider=false path. Supplying exactly one option is an error. An explicit
OpenRouter v2 startup may supply both:

```text
python -m deploy.host_agent --config ABSOLUTE_HOST_CONFIG --qualification ABSOLUTE_BINDING --qualification-sha256 OPERATOR_PINNED_SHA256
```

The operator pin is an independent trusted choice installed later in root-owned
service configuration; no evidence file approves itself. This slice does not
install those arguments or create an actual production binding. There is no
environment selector, discovery of local reports or ready=true switch.

The binding is strict version1 JSON with11exact fields, at most16384bytes. It
pins the executing release fingerprint, canonical effective provider/inference
configuration, known accepted report/reconciliation digests, private provider-key
digest, existing ledger UUID and an integer UTC validity interval of at most60days.
The model is fixed to openrouter/google/gemini-3.5-flash-lite, minimal/excluded
reasoning, existing request/output bounds and the non-resettingUSD2key cap.
The effective timeout is30seconds; the host's20second hint is not hashed as the
effective provider setting.

Beside the binding, fixed filenames accepted-report.json and reconciliation.json
must contain the original byte-identical evidence. All three, the host config and
the existing key inputs use the protected POSIX reader: absolute files outside
the release, private owner permissions, protected parents, no symlink/hardlink or
state/key aliases, with bounded stable reads. Startup also performs normal complete
release verification. The private key digest never belongs in public evidence,
repr, logs or errors. candidate_binding returns candidate bytes only; it writes,
approves, enables, settles and resets nothing.

Structural/evidence/configuration refusal occurs before SDK construction. Once
the app's single real GuardedClient/OpenRouterClient exists, validate its actual
settings, key, price limits, ledger identity/path/pages, receipt and static queue
configuration before serving. A late mismatch cleans all owned resources.

## Captured runtime behavior

The verifier retains an immutable startup snapshot and actual object references.
Runtime observations use current time, closure and in-memory bindings only.
Queue occupancy and call telemetry may change normally; they are not treated as
configuration drift. There is no qualification executor, file watch or re-hash.

Operator changes on disk become effective at restart. Deleting an evidence file
does not silently reconfigure a running Agent. Expiry, process closure, lifecycle
revocation and in-memory client/ledger/configuration drift still refuse at runtime.
Work rechecks its captured proof after lifecycle awaits; the existing final
authorization before provider POST and before exposing buffered output remain.
Stop and pending-work renewal remain independent. Closure drains the existing
provider callback and closes the lightweight verifier exactly once.

The ordinary per-POST OpenRouter key-limit/remaining-credit check and durable
allowance guard are unchanged. This verifier does not contact the provider or
assert availability, add allowance, reset theUSD2cap, settle unknown costs or
permit another qualification set. Existing uncertain reservations stay held.

## Verification frontier

Focused unit/integration checks cover strict startup inputs, zero runtime evidence
I/O, restart-only file changes, expiry across lifecycle/key/output waits, client
and custody mismatches, normal occupancy, cleanup and default-closed startup.
The native run passes under signed Python3.12.14 and Node24.22.1 from clean original
source4deaf586fc069768f83cceadd6917b5e80a18190. Its archive SHA256 is
a94a4f379509cb257a7ee9c99a2e93cc2864deff56d2d3fb6b0e7aafd79d7807; manifest SHA256 is
804243ca8138d0a402fe7594397725bf9f9c6cb6d7dc91337677f04f7a07c20c.
Actual Agent startup preserves default false, reaches signed true only with the
explicit synthetic binding, remains true after copied evidence deletion and
refuses signed readiness/work after expiry. Expired, wrong-key and altered-report
startups refuse before SDK construction. All owned resources close; existing
uncertain allowance, catalogue and manifest stay intact. No real model/SDK call.
The independent archive roundtrip verifies945files,192relative symlinks and39
contained hardlinks. All three passing native runs exit0 with empty stderr.

Full Python suite:1552passed in961.14seconds,2upstream deprecation warnings.
TypeScript:199passed across3workspaces. Ruff281files/format/pip checks pass.
Default ESLint also scans old ignored generated JavaScript copies and reports66
no-undef errors there; source lint passes with .scratch excluded.
Default Prettier reports12ignored working-ledger files; all419tracked format-supported files pass separately. The fresh review's3material timing findings were reproduced
and fixed with RED/GREEN tests, including cancellation-safe lease cleanup.

The first native build was stopped by the conservative8GiBcommit-headroom guard;
its exact container was removed and its rejected receipt is retained. The serial
rerun kept the2GiBcontainer cap and used a7GiBcommit floor plus4GiBphysical floor
(8GiBphysical required at entry). Minimum observed passing-build headroom was
7.51GiBcommit/13.33GiBphysical. No Windows memory setting changed. Task-started
Docker Desktop was stopped after confirming no remaining containers.

Machine-readable [evidence](../eval/evidence/cap06-provider-qualification-20261024.json)
records the exact profiles, hashes, results, memory receipts and rejected attempt.
Earlier native archives remain historical, unchanged evidence.

Even a passing synthetic binding is not actual-host/key qualification. Real
protected key/remaining allowance custody, host/security/systemd/reboot/capability/
metadata/log acceptance, qualified capacity, current resource/cost/rollback and
public deployment approval plus desktop/Android acceptance remain separate gates.

Subsequent [captured-client concurrency measurement](cap06-captured-capacity.md)
found and fixed a parallel pure-verification refusal without changing startup-only
hashing or the provider lock. Its new023d9f6native archive supersedes the older
functional candidate above; the original proof remains historical and unchanged.
