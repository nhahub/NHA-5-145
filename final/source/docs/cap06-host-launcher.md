# CAP-06 host Agent launcher

23 October 2026. Inactive local preparation. No unit has been installed or enabled,
and no AWS resource, production key, configuration, DNS record or certificate has
been created. Bedrock remains unqualified; the existing verifier returns false.

The explicit entry point is:

```text
/opt/shopping-copilot/python/bin/python -B -m deploy.host_agent --config /etc/shopping-copilot/host.json
```

It must execute from the selected verified release, with existing protected POSIX
configuration, separate private files and retained catalogue/allowance state as
specified in [host bootstrap](cap06-host-bootstrap.md). It refuses loading from
an active event loop. Settings and the host app are constructed synchronously,
then Uvicorn serves the app on 127.0.0.1:8000 in one process with lifespan enabled,
no proxy headers, reload or access log. There is no qualification CLI switch.
Importing the launcher does not start a service or construct a cloud SDK client.

The factory returns an owned async cleanup callback. The launcher runs it in the
server loop's finally, including server/config construction failures, startup
without lifespan, normal shutdown and cancellation. Normal lifespan cleanup and
the final callback close the shared DynamoDB SDK once after draining work. It
never constructs another app to perform cleanup. CLI failure reports only
`Host startup refused`; Uvicorn's loggers have null handlers to prevent lifespan
tracebacks exposing configuration. Other application loggers are unaffected.

`deploy/shopping-copilot-agent.service` is a separate prepared Agent-only unit,
included in fresh immutable releases. It conflicts with the legacy combined
`shopping-copilot.service`, which remains unchanged and also uses port 8000.
Do not run them together. The new unit retains the existing copilot account,
read-only release/config paths, limited state/log writes, privilege restrictions,
resource bounds, bounded restart rate and 20 second shutdown limit. Both standard
streams are discarded, matching the existing unit; durable redacted host
observability and actual shutdown timing still require deployment acceptance.

23 October continuation: [a separate inactive service bundle](cap06-host-services.md)
now includes Storefront/Caddy launchers and connects the Agent to a host target.
The Agent unit alone does not supervise the Storefront or Caddy. Real host orchestration,
real POSIX permissions, service/key provisioning, instance-role access, public
HTTPS, provider qualification, Scheduler/inventory/cost reconciliation and cloud
acceptance remain open. Preparing this entry point does not waive any gate or
authorize installation or cloud writes.

## Exact Lambda artifacts on Linux

The unchanged22 October startup/controller ZIPs passed isolated Python 3.12 import
and injected fixed-role delegation on Ubuntu 24.04.3/Python 3.12.3 and on the official
AWS Lambda Amazon Linux 2023 image, linux/amd64/Python 3.12.15:

```text
public.ecr.aws/lambda/python@sha256:25aee9bac65f131c5d090d3e3a36ccf232d65cf3e6c1dbd0bffd43ca7ce34406
```

Both external ZIP digests were checked before extraction. The AL2023 container
used no network, read-only root and three read-only input files, no host credential
or repository mount, no capabilities/new privileges, one CPU, 256 MiB RAM, 64 processes
and 128 MiB temporary memory. `-I -S -B` excluded site/checkout fallback; the probe
blocked SDK construction, socket connection and DNS. Dependency versions and
provenance, service models/CA files, fixed-role delegation and generic missing
configuration errors passed. No model or AWS API call was made.

Docker now reports Desktop 4.96.3/Engine 29.9.2 after the owner's update. Before that
update, a stale inaccessible `dockerInference` runtime endpoint prevented startup.
With Desktop stopped, only its runtime directory was renamed to
`C:/Users/pc/AppData/Local/Docker/run.stale-20261023-01`; Docker recreated it and
the Linux API recovered. The backup was preserved; no reset or data purge ran.

These are interpreter/import/delegation checks, not RIE invocation, actual Lambda
execution, IAM/OAC/event delivery or account eligibility. Evidence and exact
artifact hashes: `eval/evidence/cap06-host-launcher-20261023.json`. Ignored logs in
`outputs/cap06-linux-*` and `outputs/cap06-host-launcher-*` record these local runs.

Final host checks:84passed, including actual Uvicorn lifespan/bind failure before
any socket, with two upstream websockets deprecation warnings. Broader regression,
fresh release and browser recovery:1066passed/no skips; that collection preceded
two additional Uvicorn cases, both covered by the final host checks. Fresh review
found no actionable issues and independently ran84host tests. Target-host/cloud
acceptance was excluded; Linux logs were inspected rather than independently
reproduced, and the reviewer did not reopen external research links. Recheck
deployment-sensitive contracts before apply.
