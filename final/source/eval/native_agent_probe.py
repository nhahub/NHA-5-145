"""Disposable Linux Agent proof using synthetic read-only external authority."""

import asyncio
import copy
import hashlib
import importlib.util
import io
import json
import signal
import socket
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
from contextlib import asynccontextmanager, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

INVITATIONS = "00000000-0000-4000-8000-000000000001"
LIFECYCLE = "00000000-0000-4000-8000-000000000002"
INPUT, WORK = Path("/input"), Path("/rehearsal")
NETWORK_DENIALS = []


def isolate_network():
    connect, lookup = socket.socket.connect, socket.getaddrinfo

    def bound_connect(self, address):
        if not isinstance(address, tuple) or address[:2] not in {
            ("127.0.0.1", 4000),
            ("127.0.0.1", 8000),
        }:
            NETWORK_DENIALS.append("connect")
            raise AssertionError("External connection forbidden")
        return connect(self, address)

    def bound_lookup(host, port, *args, **kwargs):
        if host != "127.0.0.1" or port not in {4000, 8000}:
            NETWORK_DENIALS.append("lookup")
            raise AssertionError("External lookup forbidden")
        return lookup(host, port, *args, **kwargs)

    socket.socket.connect, socket.getaddrinfo = bound_connect, bound_lookup


class ReadOnlyAuthority:
    """Fixed synthetic existing rows, never an emulator for writes or real SDK."""

    def __init__(self, *, generation=1, audit_path=None):
        from agent.admission.dynamodb import _encode

        self.meta = SimpleNamespace(
            region_name="eu-north-1",
            endpoint_url="https://dynamodb.eu-north-1.amazonaws.com",
            config=SimpleNamespace(
                retries={"total_max_attempts": 1}, connect_timeout=5, read_timeout=15
            ),
        )
        self.reads = self.closed = self.forbidden = 0
        self._lock, self._audit = threading.RLock(), audit_path
        common = {"pk": "offline", "schema": 1}
        self._rows = {
            "operating#window": None,
            "meta": _encode(
                {
                    **common,
                    "sk": "meta",
                    "identity": INVITATIONS,
                    "issued": 0,
                    "lifecycle_identity": LIFECYCLE,
                }
            ),
            "lifecycle#host": _encode(
                {
                    **common,
                    "sk": "lifecycle#host",
                    "identity": LIFECYCLE,
                    "revision": 0,
                    "generation": generation,
                    "state": "ready" if generation else "stopped",
                    "observed": 0,
                    "activity": 0,
                    "deadline": 0,
                    "changed": 0,
                    "grace": 0,
                    "invitation": None,
                    "leases": {},
                    "command": None,
                    "recoverable": not bool(generation),
                    "healthy": bool(generation),
                }
            ),
        }

    def _record(self):
        if self._audit:
            temporary = self._audit.with_suffix(".tmp")
            temporary.write_text(json.dumps({"reads": self.reads, "closed": self.closed}))
            temporary.replace(self._audit)

    def get_item(self, **values):
        with self._lock:
            expected = {
                "TableName": "offline-control",
                "Key": values.get("Key"),
                "ConsistentRead": True,
            }
            key = values.get("Key", {})
            name = key.get("sk", {}).get("S")
            if (
                self.closed
                or values != expected
                or key != {"pk": {"S": "offline"}, "sk": {"S": name}}
                or name not in self._rows
            ):
                raise ValueError("Synthetic authority refused")
            self.reads += 1
            self._record()
            return {} if self._rows[name] is None else {"Item": copy.deepcopy(self._rows[name])}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        self.forbidden += 1
        raise ValueError("Synthetic authority refused")

    def close(self):
        with self._lock:
            self.closed += 1
            self._record()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request(path, *, headers=None):
    try:
        with urllib.request.urlopen(
            urllib.request.Request("http://127.0.0.1:8000" + path, headers=headers or {}),
            timeout=3,
        ) as response:
            return response.status, response.headers, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, error.headers, json.load(error)


def wait_for(child, url):
    deadline = time.monotonic() + 20
    while True:
        assert child.poll() is None, "Native child refused"
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                assert response.status == 200
            return
        except (urllib.error.URLError, TimeoutError):
            assert time.monotonic() < deadline
            time.sleep(0.05)


def agent_child(generation):
    import boto3
    import botocore.session

    def forbidden(*_, **__):
        raise AssertionError("Real SDK construction forbidden")

    boto3.client = botocore.session.Session.create_client = forbidden
    from deploy import host_agent
    from deploy.host_checks import unqualified_provider

    authority = ReadOnlyAuthority(
        generation=generation, audit_path=WORK / "state/authority-counts.json"
    )
    real_factory, observed = host_agent.create_host_app, {}
    app = None

    def record():
        assert app is not None
        model = app.state.llm_client.client
        audit = {
            "checks": observed,
            "authority_reads": authority.reads,
            "authority_closed": authority.closed,
            "authority_forbidden": authority.forbidden,
            "model_type": type(model).__name__,
            "model_attempts": len(model.call_metadata),
            "network_denials": len(NETWORK_DENIALS),
            "work_closed": app.state.lifecycle_work._closed,
            "admission_closed": app.state.admission._io._closed,
            "checks_closed": app.state.host_readiness.checks_owner._closed,
        }
        (WORK / f"state/agent-{generation}.json").write_text(json.dumps(audit))

    def assemble(settings):
        nonlocal app

        def sdk(service):
            assert service == "dynamodb"
            return authority

        app = real_factory(settings, sdk_factory=sdk)
        assert app.state.lifecycle_work._provider._verify is unqualified_provider
        original = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(value):
            try:
                async with original(value):
                    checks = app.state.host_readiness.checks_owner
                    observed.update(
                        dict(
                            zip(
                                ("release", "storefront", "admission", "allowance", "provider"),
                                await asyncio.gather(
                                    *[
                                        check()
                                        for check in checks.checks(unqualified_provider).values()
                                    ]
                                ),
                                strict=True,
                            )
                        )
                    )
                    yield
            finally:
                # Uvicorn re-raises SIGTERM after graceful lifespan completion.
                record()

        app.router.lifespan_context = lifespan
        return app

    host_agent.create_host_app = assemble
    result = host_agent.main(["--config", str(WORK / "state/host.json")])
    record()
    return result


def run(expected, fixture):
    archive = INPUT / "release.tar"
    assert sha(archive) == expected["archive_sha256"]
    release = WORK / "release"
    release.mkdir()
    with tarfile.open(archive) as package:
        assert len(package.getmembers()) < 20000
        assert sum(item.size for item in package.getmembers()) < 64 * 1024**2
        package.extractall(release, filter="data")
    fixture.command(
        sys.executable,
        "-I",
        "-m",
        "pip",
        "--isolated",
        "--disable-pip-version-check",
        "install",
        "--no-index",
        "--require-hashes",
        "--no-deps",
        "--only-binary=:all:",
        "--no-compile",
        "--no-cache-dir",
        "--target",
        str(WORK / "site"),
        "--find-links",
        "/wheels",
        "-r",
        str(release / "deploy/requirements-linux.lock"),
        timeout=90,
    )
    # Reuse the exact prior native fixture checks/configuration, without a rebuild.
    connect, lookup = socket.socket.connect, socket.getaddrinfo
    with redirect_stdout(io.StringIO()):
        fixture.runtime(expected)
    socket.socket.connect, socket.getaddrinfo = connect, lookup
    from agent.inference.ledger import AllowanceLedger
    from agent.lifecycle.readiness import _mac
    from deploy.artifact import verify
    from deploy.catalogue import catalogue_status
    from deploy.host_config import load_host_settings

    settings = load_host_settings(WORK / "state/host.json")
    assert sha(release / "release.json") == expected["manifest_sha256"]
    ledger = AllowanceLedger(
        Path(settings.inference["INFERENCE_LEDGER_PATH"]), settings.inference["INFERENCE_LEDGER_ID"]
    )
    ledger.set_enabled(True)
    before, catalogue = ledger.status(), catalogue_status(settings.catalogue)
    store = subprocess.Popen(
        child_command("store"), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    try:
        wait_for(store, "http://127.0.0.1:4000/__catalogue/v1/products")
        child = subprocess.Popen(
            child_command("agent"), stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            wait_for(child, "http://127.0.0.1:8000/health")
            assert request("/health")[2] == {"status": "ok", "service": "agent"}
            nonce = "a" * 64
            headers = {
                "x-copilot-generation": "1",
                "x-copilot-release": settings.fingerprint,
                "x-copilot-nonce": nonce,
                "x-copilot-proof": _mac(
                    settings.readiness_secret, "request", settings.fingerprint, 1, nonce
                ),
            }
            counts = WORK / "state/authority-counts.json"
            reads = json.loads(counts.read_text())["reads"]
            assert request("/health", headers={**headers, "x-copilot-proof": "0" * 64})[0] == 403
            assert json.loads(counts.read_text())["reads"] == reads
            status, response_headers, proof = request("/health", headers=headers)
            assert status == 200 and response_headers["Cache-Control"] == "no-store"
            assert proof == {
                "generation": 1,
                "release": settings.fingerprint,
                "nonce": nonce,
                "ready": False,
                "mac": _mac(
                    settings.readiness_secret, "response", settings.fingerprint, 1, nonce, False
                ),
            }
            speech = request("/speech/availability")
            assert (speech[0], speech[2]) == (401, {"detail": "Shopper identity required"})
            child.send_signal(signal.SIGTERM)
            stdout, stderr = child.communicate(timeout=10)
            assert child.returncode in {0, -signal.SIGTERM} and stdout == stderr == b""
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=5)
        positive = json.loads((WORK / "state/agent-1.json").read_text())
        assert positive["checks"] == dict(
            release=True, storefront=True, admission=True, allowance=True, provider=False
        )
        failure = subprocess.run(
            child_command("invalid"), capture_output=True, timeout=15, check=False
        )
        assert (
            failure.returncode == 1
            and failure.stdout == b""
            and failure.stderr == b"Host startup refused\n"
        )
        negative = json.loads((WORK / "state/agent-0.json").read_text())
        for value in (positive, negative):
            assert value["authority_closed"] == 1 and value["authority_forbidden"] == 0
            assert value["model_type"] == "OpenRouterClient" and value["model_attempts"] == 0
            assert value["network_denials"] == 0
            assert value["work_closed"] and value["admission_closed"] and value["checks_closed"]
        assert ledger.status() == before and catalogue_status(settings.catalogue) == catalogue
        verify(release)
        assert sha(release / "release.json") == expected["manifest_sha256"]
    finally:
        store.terminate()
        try:
            store.wait(timeout=5)
        except subprocess.TimeoutExpired:
            store.kill()
            store.wait(timeout=5)
        store.stderr.close()
    result = {
        "native_agent_started": True,
        "synthetic_authority_injected": True,
        "qualified_readiness_verified": False,
        "signed_closed_readiness_verified": True,
        "invalid_proof_before_datastore": True,
        "graceful_sigterm_verified": True,
        "sigterm_process_returncode": child.returncode,
        "generation_zero_refusal_verified": True,
        "allowance_uncertainty_preserved": True,
        "catalogue_and_manifest_preserved": True,
        "positive": positive,
        "negative": negative,
    }
    (Path("/output") / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


def child_command(mode):
    return [sys.executable, "-I", "-S", "-B", __file__, sys.argv[1], mode]


if __name__ == "__main__":
    spec = importlib.util.spec_from_file_location("native_fixture", INPUT / "release_probe.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    fixture.initialize()
    isolate_network()
    expected = fixture.profile()
    assert sha(INPUT / "release_probe.py") == expected["fixture_probe_sha256"]
    assert sha(Path(__file__)) == expected["agent_probe_sha256"]
    mode = sys.argv[2] if len(sys.argv) == 3 else "run"
    if mode == "run":
        run(expected, fixture)
    else:
        fixture.runtime_paths()
        if mode == "store":
            from deploy.host_component import main

            raise SystemExit(
                main(["--config", str(WORK / "state/store.json"), "--component", "store"])
            )
        assert mode in {"agent", "invalid"}
        raise SystemExit(agent_child(0 if mode == "invalid" else 1))
