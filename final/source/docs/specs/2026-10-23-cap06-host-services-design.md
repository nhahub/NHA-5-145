# CAP-06 inactive host service bundle

Continue the owner's requested local preparation by connecting the existing
Agent launcher, production Storefront and public Caddy profile. No service,
certificate, cloud resource, production configuration or key is installed,
activated or provisioned here. Free-plan/Stockholm/$0-cash constraints, model
qualification and full deployment approval remain unchanged.

## Launch contract

Add `python -B -m deploy.host_component --config ABSOLUTE_PATH --component
store|proxy`. It loads the existing protected HostSettings, verifies the exact
executing release, and replaces its own process with a fixed executable using
`os.execve`. It never constructs a cloud SDK or invokes a provider. Refuse invalid
CLI/settings/release/catalogue/storage/binary checks generically without secrets,
paths or dependency exceptions in CLI output.

- Store: `/usr/bin/node`, selected release's `store/src/server.js`; production,
  fixed approved public origins, lexical ranking, existing external catalogue and
  service secret only. Check the existing catalogue without creating/importing it.
  No inference ledger/key, AWS credential, evaluation flag, NODE_OPTIONS,
  LD_PRELOAD or arbitrary inherited environment reaches Node.
- Proxy: `/usr/bin/caddy run --config RELEASE/deploy/Caddyfile.public --adapter
caddyfile`. The only application environment is the selected `panel/dist` root
  and fixed retained `/var/lib/shopping-copilot/caddy` storage. No service or
  readiness secret is passed to Caddy. The storage directory must already exist,
  be outside the release, have protected nonsymlink ancestors and owner-only
  permissions, be owned by the effective service UID with rwx. Never create or
  erase it. The profile and Panel index must exist in the verified release.
  Panel paths must remain literal Caddyfile data: normalize path separators,
  reject quotes, remaining backslashes and control/DEL characters before exec;
  support ordinary spaces. This clarifies the fixed-profile handoff after review.
- Child environment starts empty except fixed PATH `/usr/bin:/bin` and
  LANG `C.UTF-8`; do not mutate the parent environment. No shell or downloader.
  Before exec, run only the selected binary's bounded five-second `--version`
  (Node) or `version` (Caddy), with the same sanitized environment, no output
  forwarded. Require Node24 >=24.13.0 and Caddy2.11.7, matching existing pins.
  Versions do not authenticate installed executables; trusted provisioning is
  still required. Standard streams remain the service unit's responsibility.

## Prepared supervision

Add Storefront and proxy units and `shopping-copilot-host.target`, package all in
the immutable release, and connect the existing Agent unit. Use the copilot
account and existing hardening. Agent retains its1GiB ceiling; the agent chooses
256MiB/64task ceilings for each new native service, subject to actual host capacity
acceptance. Caddy alone receives ambient and
bounding CAP_NET_BIND_SERVICE and may write only its retained storage; Storefront
and Agent have no capabilities. All units discard stdout/stderr as the existing
unit does. Durable bounded host diagnostics remain a separate acceptance item.

The target Wants all three units. Members are PartOf the target, so explicit
target stop/restart propagates. Order store before Agent before proxy, and every
member after and conflicting with the legacy combined unit. Do not order members
after their own target. Use independent bounded on-failure restarts; a failed
member does not claim whole-host health or force sibling failure. Only the target
is intended to be enabled on the future host. Ordering/Type=exec are process-launch
ordering, never HTTP/TLS/model readiness. Existing signed readiness remains the
authority; the default provider gate stays closed. Preserve uncertain-Action
non-replay across restart. The legacy runtime/unit is otherwise unchanged.

## Verification and limits

Test fixed exec arguments, clean/minimal environments and no parent mutation,
strict release/catalogue/path/storage/version failure, generic errors and no exec
after failure. Check unit membership/order/conflict/capabilities/hardening and
actual fresh-release inclusion. Exercise a genuine packaged production Storefront
with the generated environment on loopback, proving production private/test
boundaries and persistent state without Agent/model/SDK activation. Adapt Caddy
only; never run/start/reload/validate the public ACME profile in this preparation.

Where available, parse units with Linux systemd-analyze in a disposable root;
label this static syntax/dependency checking, not actual systemd supervision,
capability inheritance or AL2023 host acceptance. Protected POSIX reader and
actual storage ownership remain target-host checks unless separately demonstrated.
No DNS/TLS/IAM/OAC/event/account/model acceptance is implied by local wiring.
