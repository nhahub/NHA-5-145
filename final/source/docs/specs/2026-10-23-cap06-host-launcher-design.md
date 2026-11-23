# CAP-06 explicit host Agent launcher

The owner has requested continued inactive local preparation. This slice connects
the existing protected host settings and owned app factory to an explicit Python
entry point. It does not deploy, install or enable anything, change topology or
spend, qualify Bedrock, or replace the existing combined local runtime.

## Contract

- `python -B -m deploy.host_agent --config ABSOLUTE_PATH` is the only launch
  interface. Load `load_host_settings` through its real protected POSIX reader;
  construct `create_host_app(settings)` synchronously before any server loop.
  Refuse an already-running event loop before reading configuration or keys.
- The executing release must match the settings, as enforced by the factory.
  No environment selector or CLI option can select another provider, bypass the
  qualification gate, turn on reload, add workers, or change the listen address.
- Run Uvicorn on `127.0.0.1:8000`, one process, lifespan on, proxy headers off,
  access logging off and server identification off. No socket is opened by import.
  The default provider verifier remains unqualified: startup alone never makes
  signed readiness true or allows model work.
- The factory exposes an owned asynchronous cleanup callback on the returned app.
  The launcher awaits it in its server loop's `finally`, including construction
  of the server, bind errors, cancellation and failure before lifespan begins.
  Normal lifespan cleanup followed by this callback must be safe and close the
  shared SDK exactly once after draining work. Existing factory-failure cleanup
  retains its generic error and ownership guarantees.
- Report startup failure with fixed `Host startup refused` text and nonzero
  status, without paths, configuration, keys, dependency exception strings or
  traceback. Uvicorn's own error/access loggers must not bypass this redaction.
  A server that returns without ever starting is failure. Keyboard interruption
  exits nonzero after cleanup. No automatic restart or Action replay in Python.
- Add a separately prepared, hardened Agent-only systemd unit using the new
  entry point and `/etc/shopping-copilot/host.json`. It is never installed or
  enabled here. Keep the legacy combined unit unchanged. The two units must not
  run together: both bind port 8000. Storefront and Caddy supervision, key/config
  provisioning, real POSIX acceptance and full host deployment remain open.
- Include the new unit in the immutable release allowlist. A fresh general
  release build must verify it and the Python entry point are packaged.

## Implementation choices made by the agent

Use the installed Uvicorn `Config`/`Server.serve` API with a prebuilt app, inside
one `asyncio.run`, so final cleanup stays on the server loop. Use explicit null
handlers only for Uvicorn's loggers; do not suppress unrelated application loggers.
Use the existing test SDK and synthetic release fixtures to exercise resource
ownership and closed qualification without credentials, sockets or model calls.
The existing supported shutdown bound and hardened unit template are retained.

## Acceptance and evidence limits

Tests must cover pre-loop ordering, loop rejection before key reads, unknown CLI
switches, generic errors from load/factory/server, failure before lifespan and
after lifespan initialization, normal shutdown and cancellation, closed provider
readiness/no inference charges, SDK close-once and fixed server settings. Inspect
the prepared unit and fresh immutable release as well. This is local wiring
evidence, not a real systemd/POSIX/IAM/EC2 or public TLS acceptance claim.

The unchanged startup/controller ZIPs have separately passed isolated imports
and injected fixed-role delegation on the official Amazon Linux 2023 Python 3.12
image. That check is not RIE invocation or AWS integration acceptance.
