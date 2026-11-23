"""Finite owner diagnostics: a vocabulary of events, never arbitrary child output."""

import json
import time
from pathlib import Path

EVENTS = {"starting", "ready", "unhealthy", "stopped", "restarting", "refused"}
SERVICES = {"all", "agent", "store", "panel"}


class Diagnostics:
    def __init__(self, directory, *, maximum_bytes=65536, backups=2):
        if not 128 <= maximum_bytes <= 1048576 or not 1 <= backups <= 10:
            raise ValueError("Finite log bounds required")
        self.directory = Path(directory).resolve()
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = self.directory / "runtime.jsonl"
        self.maximum_bytes, self.backups = maximum_bytes, backups
        now = time.time()
        for path in self.directory.glob("runtime.jsonl*"):
            if path.is_symlink():
                raise ValueError("Log links are not allowed")
            if now - path.stat().st_mtime > 7 * 86400:
                path.unlink()

    def record(self, event, service="all"):
        if event not in EVENTS or service not in SERVICES:
            raise ValueError("Diagnostic event not supported")
        line = json.dumps({"time": int(time.time()), "event": event, "service": service}) + "\n"
        if self.path.exists() and self.path.stat().st_size + len(line) > self.maximum_bytes:
            for number in range(self.backups, 0, -1):
                previous = self.path if number == 1 else Path(str(self.path) + f".{number - 1}")
                target = Path(str(self.path) + f".{number}")
                if previous.exists():
                    previous.replace(target)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(line)
        self.path.chmod(0o600)
