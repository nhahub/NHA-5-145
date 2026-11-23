import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


class ServiceController:
    """Evaluation-only process restart; the fixture owns these exact children."""

    def __init__(self, processes, commands, environment, creation_flags):
        self.processes = processes
        self.commands = commands
        self.environment = environment
        self.creation_flags = creation_flags

    def restart(self, service: str) -> None:
        index = {"agent": 0, "store": 1}[service]
        process = self.processes[index]
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        self.processes[index] = subprocess.Popen(
            self.commands[index],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=self.creation_flags,
            env=self.environment,
        )
        _wait_for("http://127.0.0.1:8000/health" if index == 0 else "http://127.0.0.1:4000/")


def _pnpm_command() -> str:
    command = shutil.which("pnpm")
    if command is None:
        raise RuntimeError("pnpm is required to run the local browser evaluation")
    return command


def service_commands(node: Path) -> tuple[list[str], ...]:
    return (
        [
            sys.executable,
            "-m",
            "uvicorn",
            "agent.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        [
            str(node),
            str(ROOT / "store" / "node_modules" / "tsx" / "dist" / "cli.mjs"),
            str(ROOT / "store" / "src" / "server.ts"),
        ],
        [
            str(node),
            str(ROOT / "panel" / "node_modules" / "vite" / "bin" / "vite.js"),
            str(ROOT / "panel"),
            "--host",
            "127.0.0.1",
            "--port",
            "4100",
        ],
    )


def service_environment(
    base: Mapping[str, str] | None = None,
    *,
    real_model: bool = False,
    test_clock: bool = False,
    state_directory: Path | None = None,
) -> dict[str, str]:
    """Return the isolated environment used by the local evaluation services."""
    environment = dict(os.environ if base is None else base)
    environment["COPILOT_SERVICE_SECRET"] = secrets.token_hex(32)
    environment["COPILOT_EVALUATION"] = "1"
    if state_directory is not None:
        environment["AGENT_STATE_FILE"] = str(state_directory / "agent-state.sqlite")
        environment["COPILOT_STATE_DB"] = str(state_directory / "storefront-state.sqlite")
    if real_model:
        if environment.get("LLM_PROVIDER") in {None, "scripted"} or not environment.get(
            "LLM_MODEL"
        ):
            raise ValueError(
                "Real browser evaluation requires an explicitly selected real provider"
            )
        return environment
    environment["LLM_PROVIDER"] = "scripted"
    environment["LLM_MODEL"] = "scripted-v1"
    if test_clock:
        environment["EVAL_TEST_CLOCK"] = "1"
    return environment


def _wait_for(url: str, timeout_seconds: float = 20) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:  # noqa: S310 - fixed local evaluation URLs
                if response.status < 500:
                    return
        except (URLError, TimeoutError):
            time.sleep(0.1)
    raise RuntimeError(f"Local service did not become ready: {url}")


@contextmanager
def local_services(
    *,
    real_model: bool = False,
    test_clock: bool = False,
    agent_app: str = "agent.app:app",
) -> Iterator[ServiceController]:
    pnpm = _pnpm_command()
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js is required to run the local browser evaluation")
    for port in (4000, 4100, 8000):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(
                    f"Evaluation port {port} is occupied; refusing to reset another service"
                )
    subprocess.run(  # noqa: S603 - fixed local command without a shell
        [pnpm, "--filter", "@shopping-copilot/bridge", "build"],
        cwd=ROOT,
        check=True,
    )
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    commands = service_commands(Path(node))
    commands[0][3] = agent_app
    with TemporaryDirectory(prefix="copilot-eval-catalogue-") as database_directory:
        # The Agent and the Storefront save state here, never under work/. Restarts of one
        # service reuse the same files, so a restart keeps what was saved.
        catalogue_file = str(Path(database_directory) / "catalogue.sqlite")
        subprocess.run(  # noqa: S603 - owned local importer and temporary database
            [
                str(node),
                str(ROOT / "store/node_modules/tsx/dist/cli.mjs"),
                str(ROOT / "store/scripts/catalogue-import.ts"),
                "--database",
                catalogue_file,
            ],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
        environment = service_environment(
            real_model=real_model,
            test_clock=test_clock,
            state_directory=Path(database_directory),
        )
        environment["COPILOT_CATALOGUE_DB"] = catalogue_file
        processes = [
            subprocess.Popen(  # noqa: S603 - fixed local commands without a shell
                command,
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
                env=environment,
            )
            for command in commands
        ]
        try:
            _wait_for("http://127.0.0.1:8000/health")
            _wait_for("http://127.0.0.1:4000/")
            _wait_for("http://127.0.0.1:4100/")
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("An evaluation service exited during startup")
            yield ServiceController(processes, commands, environment, creation_flags)
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
