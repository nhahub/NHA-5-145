"""Owned loopback HTTPS stack with a network-free injected model."""

import base64
import hashlib
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from agent.admission.runtime import FIELDS, AdmissionPolicy
from agent.admission.store import InvitationStore
from agent.inference.ledger import AllowanceLedger
from deploy.artifact import build
from eval.tests.test_release import seed_catalogue

ROOT = Path(__file__).resolve().parents[2]
PANEL = "https://panel.copilot.test:4443"
STORE = "https://store.copilot.test:4443"
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(arguments, **kwargs):
    return subprocess.run(arguments, check=True, capture_output=True, creationflags=FLAGS, **kwargs)


def certificate(folder):
    openssl = shutil.which("openssl")
    if not openssl:
        raise RuntimeError("OpenSSL required for disposable local certificate")
    key, cert = folder / "leaf.key", folder / "leaf.pem"
    run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-noenc",
            "-days",
            "1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/CN=panel.copilot.test",
            "-addext",
            "subjectAltName=DNS:panel.copilot.test,DNS:store.copilot.test",
        ]
    )
    key.chmod(0o600)
    public = run([openssl, "x509", "-in", str(cert), "-pubkey", "-noout"]).stdout
    der = run([openssl, "pkey", "-pubin", "-outform", "DER"], input=public).stdout
    return key, cert, base64.b64encode(hashlib.sha256(der).digest()).decode()


@contextmanager
def stack(folder, *, caddy_path=None):
    folder = Path(folder).resolve()
    folder.mkdir(exist_ok=False)
    processes = {}
    key = None
    for port in (4000, 8000, 4443):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError("Capacity ports occupied; refuse to replace another service")
    # Only the small OS environment is inherited. In particular, no provider key
    # or dotenv configuration can enter this load-test process tree.
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper()
        in {
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "PATHEXT",
            "TEMP",
            "TMP",
            "HOME",
            "USERPROFILE",
            "LOCALAPPDATA",
            "APPDATA",
            "PNPM_HOME",
        }
    }
    env.update(
        PYTHON_DOTENV_DISABLED="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(ROOT),
        COPILOT_ENV="production",
        COPILOT_CAPACITY_REHEARSAL="1",
        CAPACITY_OUTPUT=str(folder),
        COPILOT_SERVICE_SECRET=secrets.token_hex(32),
        COPILOT_PANEL_ORIGIN=PANEL,
        COPILOT_STORE_ORIGIN=STORE,
        COPILOT_AGENT_ORIGIN=PANEL,
        COPILOT_STORE_PRIVATE_URL="http://127.0.0.1:4000",
        LLM_PROVIDER="groq",
        LLM_MODEL="test-model",
        GROQ_API_KEY="capacity-fixture-unused",
        CATALOGUE_RETRIEVAL_ENABLED="0",
        COPILOT_CATALOGUE_DB=str(folder / "catalogue.sqlite"),
        INFERENCE_PROVIDER="groq",
        INFERENCE_MODEL="test-model",
        INFERENCE_INPUT_USD_PER_MILLION="0.3",
        INFERENCE_OUTPUT_USD_PER_MILLION="2.5",
        INFERENCE_MAX_ACTIVE="2",
        INFERENCE_MAX_WAITING="3",
        INFERENCE_WAIT_SECONDS="8",
        INFERENCE_MAXIMUM_PAGES="1024",
        INFERENCE_LEDGER_PATH=str(folder / "allowance.sqlite"),
        ADMISSION_DB_PATH=str(folder / "admission.sqlite"),
    )
    invitations = InvitationStore(
        folder / "admission.sqlite", InvitationStore.initialize(folder / "admission.sqlite")
    )
    policy = AdmissionPolicy(invitations)
    env["ADMISSION_DB_ID"] = invitations.identity
    env.update({"ADMISSION_" + name: str(getattr(policy, field)) for field, name in FIELDS.items()})
    env["INFERENCE_LEDGER_ID"] = AllowanceLedger.initialize(
        folder / "allowance.sqlite", Decimal("5")
    )
    ledger = AllowanceLedger(folder / "allowance.sqlite", env["INFERENCE_LEDGER_ID"])
    try:
        key, cert, pin = certificate(folder)
        # The source/build process receives only fixture/public settings.
        saved = dict(os.environ)
        try:
            os.environ.clear()
            os.environ.update(env)
            build(ROOT, folder / "release")
        finally:
            os.environ.clear()
            os.environ.update(saved)
        seed_catalogue(folder / "catalogue.sqlite")
        release = folder / "release"
        env.update(
            COPILOT_TLS_CERT=cert.as_posix(),
            COPILOT_TLS_KEY=key.as_posix(),
            COPILOT_PANEL_ROOT=(release / "panel/dist").as_posix(),
            COPILOT_CADDY_STORAGE=(folder / "caddy-storage").as_posix(),
        )
        caddy = (
            Path(caddy_path).resolve()
            if caddy_path is not None
            else ROOT / ".scratch/cap04-cloud-readiness/tools/caddy.exe"
        )
        if not caddy.is_file():
            raise RuntimeError("Previously verified local Caddy binary is required")
        commands = {
            "store": [shutil.which("node"), str(release / "store/src/server.js")],
            "agent": [
                sys.executable,
                "-B",
                "-m",
                "uvicorn",
                "eval.capacity.application:create_capacity_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--no-access-log",
            ],
            "proxy": [
                str(caddy),
                "run",
                "--config",
                str(ROOT / "deploy/Caddyfile"),
                "--adapter",
                "caddyfile",
            ],
        }
        for name, args in commands.items():
            processes[name] = subprocess.Popen(
                args,
                cwd=release,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=FLAGS,
            )
        for port in (4000, 8000, 4443):
            deadline = time.monotonic() + 25
            while True:
                if any(p.poll() is not None for p in processes.values()):
                    raise RuntimeError("Capacity service exited at startup")
                with socket.socket() as probe:
                    if probe.connect_ex(("127.0.0.1", port)) == 0:
                        break
                if time.monotonic() > deadline:
                    raise RuntimeError("Capacity readiness deadline exceeded")
                time.sleep(0.1)
        yield invitations, ledger, processes, pin
    finally:
        for process in reversed(list(processes.values())):
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=FLAGS,
                        check=False,
                    )
                else:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        if key is not None:
            key.unlink(missing_ok=True)
