"""Native startup capture with synthetic custody; never deployed qualification."""

import asyncio
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

INPUT, WORK, OUTPUT = Path("/input"), Path("/rehearsal"), Path("/output")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_private(path, raw):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(raw)


def qualification_arguments(settings, path, *, issued_at, expires_at):
    from deploy.provider_binding import candidate_binding

    _write_private(path, candidate_binding(settings, issued_at=issued_at, expires_at=expires_at))
    return ["--qualification", str(path), "--qualification-sha256", sha(path)]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def child(base, mode, arguments):
    import boto3
    import botocore.session

    def forbidden(*_, **__):
        raise AssertionError("Real SDK construction forbidden")

    boto3.client = botocore.session.Session.create_client = forbidden
    from agent.lifecycle.store import LifecycleUnavailable
    from deploy import host_agent, provider_binding

    authority = base.ReadOnlyAuthority(generation=1)
    original_factory = host_agent.create_host_app
    app, private_reads, expired_work = None, [], []

    def record():
        model = app.state.llm_client.client if app is not None else None
        gate = app.state.lifecycle_work._provider if app is not None else None
        result = {
            "app_constructed": app is not None,
            "actual_verifier_selected": gate is not None
            and type(gate._qualified).__name__ == "ProviderQualification",
            "no_qualification_io_worker": gate is None or not hasattr(gate._qualified, "_io"),
            "runtime_private_read_attempts": len(private_reads),
            "expiry_work_refused": expired_work == [True],
            "model_attempts": len(model.call_metadata) if model is not None else 0,
            "network_denials": len(base.NETWORK_DENIALS),
            "authority_reads": authority.reads,
            "authority_closed": authority.closed,
            "authority_forbidden": authority.forbidden,
            "verifier_closed": gate is not None and gate._qualified._closed,
            "work_closed": app is not None and app.state.lifecycle_work._closed,
            "admission_closed": app is not None and app.state.admission._io._closed,
        }
        (WORK / f"state/qualification-{mode}.json").write_text(json.dumps(result))

    def assemble(settings, **options):
        nonlocal app
        assert set(options) == {"qualification"}
        app = original_factory(
            settings,
            sdk_factory=lambda service: authority if service == "dynamodb" else forbidden(),
            **options,
        )
        assert (
            type(app.state.lifecycle_work._provider._qualified).__name__ == "ProviderQualification"
        )
        original = app.router.lifespan_context

        def no_runtime_read(*_):
            private_reads.append(True)
            raise AssertionError("Runtime qualification private read")

        # Startup already used the real protected reader. These guards prove
        # serving never returns to that path, including after file deletion.
        provider_binding._entry = no_runtime_read
        provider_binding.ProviderBinding._startup = no_runtime_read

        async def check_expiry():
            end = options["qualification"]._initial.expires_at
            await asyncio.sleep(max(0, end - time.time()) + 0.05)
            try:
                await app.state.lifecycle_work.check()
            except LifecycleUnavailable:
                expired_work.append(True)
            (WORK / "state/qualification-expiry-observed.json").write_text(json.dumps(expired_work))

        @asynccontextmanager
        async def lifespan(value):
            try:
                async with original(value):
                    task = asyncio.create_task(check_expiry())
                    try:
                        yield
                    finally:
                        if not task.done():
                            task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
            finally:
                record()

        app.router.lifespan_context = lifespan
        return app

    host_agent.create_host_app = assemble
    result = host_agent.main(["--config", str(WORK / "state/host.json"), *arguments])
    record()
    return result


def signed_readiness(base, settings):
    from agent.lifecycle.readiness import _mac

    nonce = "b" * 64
    status, headers, body = base.request(
        "/health",
        headers={
            "x-copilot-generation": "1",
            "x-copilot-release": settings.fingerprint,
            "x-copilot-nonce": nonce,
            "x-copilot-proof": _mac(
                settings.readiness_secret, "request", settings.fingerprint, 1, nonce
            ),
        },
    )
    assert status == 200 and headers["Cache-Control"] == "no-store" and type(body["ready"]) is bool
    assert body == {
        "generation": 1,
        "release": settings.fingerprint,
        "nonce": nonce,
        "ready": body["ready"],
        "mac": _mac(
            settings.readiness_secret, "response", settings.fingerprint, 1, nonce, body["ready"]
        ),
    }
    return body["ready"]


def command(mode, arguments):
    return [sys.executable, "-I", "-S", "-B", __file__, sys.argv[1], mode, *arguments]


def run(expected, fixture, base):
    # Preserve the full existing default-false/startup/shutdown/generation0 proof.
    base.run(expected, fixture)
    baseline = json.loads((OUTPUT / "result.json").read_bytes())
    (OUTPUT / "default-agent.json").write_text(json.dumps(baseline, indent=2) + "\n")
    from agent.inference.ledger import AllowanceLedger
    from deploy.artifact import verify
    from deploy.catalogue import catalogue_status
    from deploy.host_config import load_host_settings

    settings = load_host_settings(WORK / "state/host.json")
    ledger = AllowanceLedger(
        Path(settings.inference["INFERENCE_LEDGER_PATH"]), settings.inference["INFERENCE_LEDGER_ID"]
    )
    before = ledger.status(), catalogue_status(settings.catalogue)
    directory = WORK / "state/qualification"
    directory.mkdir(mode=0o700)
    for name, key in [
        ("accepted-report.json", "accepted_report_sha256"),
        ("reconciliation.json", "reconciliation_sha256"),
    ]:
        assert sha(INPUT / name) == expected[key] and (INPUT / name).stat().st_size <= 1024**2
        _write_private(directory / name, (INPUT / name).read_bytes())
    store = subprocess.Popen(
        base.child_command("store"), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    try:
        base.wait_for(store, "http://127.0.0.1:4000/__catalogue/v1/products")
        now = int(time.time())
        arguments = qualification_arguments(
            settings, directory / "active.json", issued_at=now, expires_at=now + 10
        )
        process = subprocess.Popen(
            command("qualified", arguments), stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            base.wait_for(process, "http://127.0.0.1:8000/health")
            assert signed_readiness(base, settings) is True
            (directory / "accepted-report.json").unlink()
            assert signed_readiness(base, settings) is True
            deadline = time.monotonic() + 12
            while not (WORK / "state/qualification-expiry-observed.json").exists():
                assert process.poll() is None and time.monotonic() < deadline
                time.sleep(0.05)
            assert signed_readiness(base, settings) is False
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode in {0, -signal.SIGTERM} and stdout == stderr == b""
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
        positive = json.loads((WORK / "state/qualification-qualified.json").read_bytes())
        assert all(
            positive[key]
            for key in [
                "app_constructed",
                "actual_verifier_selected",
                "no_qualification_io_worker",
                "expiry_work_refused",
                "verifier_closed",
                "work_closed",
                "admission_closed",
            ]
        )
        assert (
            positive["runtime_private_read_attempts"]
            == positive["model_attempts"]
            == positive["network_denials"]
            == positive["authority_forbidden"]
            == 0
        )
        assert positive["authority_closed"] == 1
        _write_private(
            directory / "accepted-report.json", (INPUT / "accepted-report.json").read_bytes()
        )
        failures = {}
        for mode in ("expired", "wrong-key", "bad-evidence"):
            now = int(time.time())
            args = qualification_arguments(
                settings,
                directory / f"{mode}.json",
                issued_at=now - 100,
                expires_at=now - 1 if mode == "expired" else now + 100,
            )
            key_path = settings.private_files[-1]
            original_key = key_path.read_bytes()
            if mode == "wrong-key":
                key_path.write_bytes(b"changed-synthetic-key-" + b"x" * 64)
            elif mode == "bad-evidence":
                (directory / "accepted-report.json").write_bytes(
                    (INPUT / "accepted-report.json").read_bytes() + b" "
                )
            failed = subprocess.run(
                command(mode, args), capture_output=True, timeout=15, check=False
            )
            assert (
                failed.returncode == 1
                and failed.stdout == b""
                and failed.stderr == b"Host startup refused\n"
            )
            observation = json.loads((WORK / f"state/qualification-{mode}.json").read_bytes())
            assert (
                not observation["app_constructed"]
                and observation["authority_reads"]
                == observation["model_attempts"]
                == observation["runtime_private_read_attempts"]
                == 0
            )
            failures[mode] = observation
            key_path.write_bytes(original_key)
        assert (ledger.status(), catalogue_status(settings.catalogue)) == before
        verify(WORK / "release")
        assert sha(WORK / "release/release.json") == expected["manifest_sha256"]
    finally:
        store.terminate()
        try:
            store.wait(timeout=5)
        except subprocess.TimeoutExpired:
            store.kill()
            store.wait(timeout=5)
        store.stderr.close()
    result = {
        "default_agent": baseline,
        "explicit_synthetic_binding_ready": True,
        "startup_only_private_hashing_verified": True,
        "runtime_evidence_deletion_does_not_reconfigure": True,
        "expiry_blocks_signed_readiness_and_work": True,
        "qualification_io_worker_created": False,
        "positive": positive,
        "startup_refusals": failures,
        "allowance_catalogue_manifest_preserved": True,
        "actual_host_or_key_qualified": False,
        "real_provider_requests": 0,
        "real_sdk_requests": 0,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    fixture = load("release_fixture", INPUT / "release_probe.py")
    fixture.initialize()
    base = load("agent_fixture", INPUT / "agent_probe.py")
    base.isolate_network()
    expected = fixture.profile()
    assert sha(Path(__file__)) == expected["qualification_probe_sha256"]
    assert sha(INPUT / "agent_probe.py") == expected["agent_probe_sha256"]
    assert sha(INPUT / "release_probe.py") == expected["fixture_probe_sha256"]
    mode = sys.argv[2] if len(sys.argv) > 2 else "run"
    if mode == "run":
        run(expected, fixture, base)
    else:
        fixture.runtime_paths()
        assert mode in {"qualified", "expired", "wrong-key", "bad-evidence"}
        raise SystemExit(child(base, mode, sys.argv[3:]))
