"""Loopback lifecycle rehearsal. No AWS SDK, remote control or cloud resources."""

import argparse
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path

import uvicorn
from dotenv import dotenv_values

from agent.admission.store import InvitationStore
from agent.lifecycle import Lifecycle
from agent.lifecycle.http import create_waiting_app
from deploy.runtime import ReleaseRuntime


class LocalHost:
    """One designated built release, standing in for the one EC2 instance.

    A separate controller owns start/stop; HTTP never waits on these futures.
    Only this object owns service processes; it survives coordinator reopens.
    """

    def __init__(self, release, config, logs):
        self.release, self.config, self.logs = release, config, logs
        self.runtime = None
        self.state = "stopped"
        self.commands = set()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None

    def observe(self):
        if self.future is not None and self.future.done():
            try:
                self.future.result()
            except Exception:
                # An unsuccessful command is not proof of process termination.
                # Keep the host fenced until stopped is actually established.
                self.state = "unknown"
                return self.state, False
        if self.state == "running" and self.runtime is not None:
            try:
                self.runtime.check_health()
                return "running", True
            except RuntimeError:
                return "running", False
        return self.state, False

    def start(self, generation):
        command = ("start", generation)
        if command in self.commands:
            return
        self.commands.add(command)
        self.state = "pending"

        def boot():
            self.runtime = ReleaseRuntime(self.release, self.config, self.logs, local=True).start()
            if self.state == "pending":
                self.state = "running"

        self.future = self.executor.submit(boot)

    def stop(self, generation):
        command = ("stop", generation)
        if command in self.commands:
            return
        self.commands.add(command)
        self.state = "stopping"

        def halt():
            if self.runtime is not None:
                self.runtime.close()
                self.runtime = None
            self.state = "stopped"

        self.future = self.executor.submit(halt)

    def close(self):
        self.executor.shutdown(wait=True)
        if self.runtime is not None:
            self.runtime.close()


def authority(config):
    values = dotenv_values(config, interpolate=False)
    if values.get("COPILOT_ENV") != "local-rehearsal":
        raise ValueError("Only local rehearsal is supported")
    invitations = InvitationStore(Path(values["ADMISSION_DB_PATH"]), values["ADMISSION_DB_ID"])
    return Lifecycle(Path(values["LIFECYCLE_DB_PATH"]), values["LIFECYCLE_DB_ID"], invitations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("initialize")
    initialize.add_argument("--path", type=Path, required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--release", type=Path, required=True)
    serve.add_argument("--config", type=Path, required=True)
    serve.add_argument("--logs", type=Path, required=True)
    serve.add_argument("--prewarm", action="store_true")
    args = parser.parse_args()
    if args.command == "initialize":
        print(Lifecycle.initialize(args.path))
        return
    life = authority(args.config)
    host = LocalHost(args.release, args.config, args.logs)
    server = uvicorn.Server(
        uvicorn.Config(
            create_waiting_app(life, origin="http://localhost:4200"),
            host="127.0.0.1",
            port=4200,
            access_log=False,
            log_level="critical",
        )
    )
    finished = threading.Event()

    def reconcile():
        while not finished.is_set():
            # Never recreate authority or issue a command on storage failure.
            with suppress(Exception):
                life.tick(host)
            finished.wait(1)

    if args.prewarm:
        life.manual_start()
    worker = threading.Thread(target=reconcile, daemon=True)
    worker.start()
    try:
        server.run()
    finally:
        finished.set()
        worker.join(timeout=5)
        host.close()


if __name__ == "__main__":
    main()
