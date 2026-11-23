"""Owner-controlled fixed service processes. No remote command or restart endpoint."""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from agent.admission.store import InvitationStore
from agent.inference.ledger import AllowanceLedger
from deploy.catalogue import catalogue_status
from deploy.configuration import preflight
from deploy.diagnostics import Diagnostics

PORTS = {"store": 4000, "agent": 8000, "panel": 4100}
HEALTH = {
    "store": "http://127.0.0.1:4000/__catalogue/v1/products",
    "agent": "http://127.0.0.1:8000/health",
    "panel": "http://127.0.0.1:4100/",
}


class ReleaseRuntime:
    def __init__(self, release, config, logs, *, local=False, service="all"):
        if service not in {"all", *PORTS} or (service == "panel" and not local):
            raise ValueError("Unsupported service")
        self.release = Path(release).resolve(strict=True)
        self.config, self.local = config, local
        if Path(logs).resolve().is_relative_to(self.release):
            raise ValueError("Logs must be external to releases")
        self.diagnostics = Diagnostics(logs)
        self.values = preflight(self.release, config, local=local)
        self.services = (
            (["store", "agent", "panel"] if local else ["store", "agent"])
            if service == "all"
            else [service]
        )
        self.processes = {}

    def _spawn(self, service):
        port = PORTS[service]
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError("Service port occupied; refusing to replace another process")
        commands = {
            "store": [shutil.which("node"), str(self.release / "store/src/server.js")],
            "agent": [
                sys.executable,
                "-m",
                "uvicorn",
                "agent.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--no-access-log",
            ],
            "panel": [sys.executable, "-m", "deploy.static"],
        }
        environment = {
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
            }
        }
        environment.update(self.values)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        self.processes[service] = subprocess.Popen(
            commands[service],
            cwd=self.release,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.diagnostics.record("starting", service)

    def start(self):
        try:
            for service in self.services:
                self._spawn(service)
            self._wait_ready()
            return self
        except BaseException:
            self.close()
            raise

    def _wait_ready(self):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if any(process.poll() is not None for process in self.processes.values()):
                raise RuntimeError("Service failed to start")
            try:
                self.check_health()
                self.diagnostics.record("ready")
                return
            except RuntimeError:
                time.sleep(0.1)
        raise RuntimeError("Service readiness deadline exceeded")

    def check_health(self):
        try:
            if any(process.poll() is not None for process in self.processes.values()):
                raise RuntimeError("Child exited")
            with httpx.Client(timeout=2, trust_env=False) as client:
                for service in self.services:
                    if client.get(HEALTH[service]).status_code != 200:
                        raise RuntimeError("Health failed")
            catalogue_status(self.values["COPILOT_CATALOGUE_DB"])
            InvitationStore(Path(self.values["ADMISSION_DB_PATH"]), self.values["ADMISSION_DB_ID"])
            AllowanceLedger(
                Path(self.values["INFERENCE_LEDGER_PATH"]), self.values["INFERENCE_LEDGER_ID"]
            ).status()
        except Exception:
            self.diagnostics.record("unhealthy")
            raise RuntimeError("Release unhealthy") from None

    def restart(self, service):
        if service not in self.services:
            raise ValueError("Service not owned by this runtime")
        preflight(self.release, self.config, local=self.local)
        self.diagnostics.record("restarting", service)
        self._stop(service)
        self._spawn(service)
        self._wait_ready()

    def _stop(self, service):
        process = self.processes[service]
        if process.poll() is None:
            if os.name == "nt":
                # A Windows venv launcher may own a second Python process. Stop
                # this exact owned tree before its launcher can orphan the child.
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with socket.socket() as probe:
                    if probe.connect_ex(("127.0.0.1", PORTS[service])) != 0:
                        break
                time.sleep(0.05)

    def close(self):
        for service in reversed(list(self.processes)):
            self._stop(service)
        self.diagnostics.record("stopped")

    def __enter__(self):
        return self.start()

    def __exit__(self, *_args):
        self.close()
