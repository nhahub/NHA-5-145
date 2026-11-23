"""The host Agent's event records, written to its private log folder off the request path."""

import json
import queue
import threading
import time
from pathlib import Path

from deploy.host_diagnostics import append_line

NAMES = ("events.jsonl", "events.jsonl.1", "events.jsonl.2")
DIRECTORY = Path("/var/log/shopping-copilot/agent")  # LogsDirectory= of the agent unit
FILE_BYTES = 5 * 1024 * 1024 // 3  # three rotating files, about 5 MB in total
# Owner-only debug switch: `sudo touch` this root-owned file over SSH to record
# Shopper text for 60 minutes. The Agent can read /etc/shopping-copilot but never
# write it, so it cannot turn the switch on itself. Debug records stay on the host.
DEBUG_MARKER = Path("/etc/shopping-copilot/debug-logging")


class HostFileSink:
    """Queues records and appends them from one background thread.

    A request only ever puts a record on a bounded queue, so a slow or stalled disk
    cannot slow a Shopper. When the queue is full the record is refused, and the
    event log counts that instead of failing the request. Write errors on the
    background thread are counted in ``failures``.
    """

    def __init__(
        self, directory: Path = DIRECTORY, *, file_bytes: int = FILE_BYTES, capacity: int = 10_000
    ):
        self.directory = Path(directory)
        self.file_bytes = file_bytes
        self.failures = 0
        self._queue: queue.Queue = queue.Queue(maxsize=capacity)
        threading.Thread(target=self._drain, name="event-log-writer", daemon=True).start()

    def write(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n"
        self._queue.put_nowait(line.encode("ascii"))  # queue.Full is counted by the caller

    def flush(self) -> None:
        """Wait until every queued record has been written or failed."""
        self._queue.join()

    def _drain(self) -> None:
        while True:
            encoded = self._queue.get()
            try:
                append_line(
                    self.directory,
                    NAMES,
                    encoded,
                    maximum_bytes=self.file_bytes,
                    now=int(time.time()),
                    sync=False,  # request records are frequent; durability is best effort
                )
            except Exception:
                self.failures += 1
            finally:
                self._queue.task_done()
