"""Ships the host Agent's event records to CloudWatch Logs from its private log file.

The file is the source of truth: records are written there first (deploy.host_event_log)
and this shipper sends new complete lines in batches. It remembers its place by file
identity (device, file number and first line) plus offset, and the time of the last
record it sent, so a restart resumes without gaps, a rotated or pruned file never causes
records to be sent twice, and an unreachable CloudWatch loses nothing. Delivery is
at-least-once: a crash in the instant between sending a batch and saving the checkpoint
can send that one batch again. Debug records are never sent.

On the host, files are read and the checkpoint written through descriptors with the same
checks as the host's other private files (no symlinks, one link, owned by the Agent, not
readable by others). The plain path exists only so the logic can be tested off Linux.
"""

import hashlib
import json
import os
import stat
import threading
import time
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import boto3
from botocore.config import Config

from deploy.host_event_log import DIRECTORY, FILE_BYTES, NAMES

GROUP = "/scpilot/agent-events"
CHECKPOINT = Path("/var/lib/shopping-copilot/agent/log-shipper.json")
INTERVAL_SECONDS = 15
# CloudWatch accepts at most 10,000 events and 1,048,576 bytes (26 bytes overhead each),
# events of at most 256 KB, no older than 14 days or more than 2 hours ahead, and a
# batch spanning at most 24 hours. These bounds stay inside all of that.
BATCH_EVENTS = 1000
BATCH_BYTES = 900_000
EVENT_BYTES = 250_000
OLDEST_MS = 13 * 24 * 3600 * 1000
NEWEST_MS = 90 * 60 * 1000
SPAN_MS = 23 * 3600 * 1000
OVERHEAD = 26


def logs_client():
    """The host's CloudWatch Logs client, pinned like its other AWS clients."""
    return boto3.client(
        "logs",
        region_name="eu-north-1",
        endpoint_url="https://logs.eu-north-1.amazonaws.com",
        use_ssl=True,
        verify=True,
        config=Config(
            connect_timeout=5,
            read_timeout=15,
            proxies={},
            retries={"mode": "standard", "total_max_attempts": 1},
            ignore_configured_endpoint_urls=True,
        ),
    )


@dataclass(frozen=True)
class Position:
    """How far shipping got: a file, an offset in it, and the last record's time."""

    device: int | None = None
    inode: int | None = None
    head: str | None = None
    offset: int = 0
    last_ms: int = -1


@dataclass(frozen=True)
class _Line:
    timestamp: int | None  # None for debug or unreadable lines, which are never sent
    text: str
    after: Position


class Shipper:
    def __init__(
        self,
        directory=DIRECTORY,
        client=None,
        *,
        stream: str,
        group: str = GROUP,
        checkpoint=CHECKPOINT,
        clock=time.time,
    ):
        self.directory = Path(directory)
        self.client = client
        self.group = group
        self.stream = stream
        self.checkpoint = Path(checkpoint)
        self.clock = clock
        self.failures = 0
        self.dropped = 0
        self._stop = threading.Event()
        self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def poll(self) -> bool:
        """Send every complete record written since the checkpoint; True if nothing is left."""
        now_ms = int(self.clock() * 1000)
        batch, size, saved = [], 0, self._load()
        position = saved
        for line in self._lines(saved):
            if not self._sendable(line, now_ms):
                position = line.after
                continue
            event = {"timestamp": line.timestamp, "message": line.text}
            cost = len(line.text.encode()) + OVERHEAD
            if batch and (
                len(batch) >= BATCH_EVENTS
                or size + cost > BATCH_BYTES
                or line.timestamp - batch[0]["timestamp"] > SPAN_MS
            ):
                if not self._flush(batch, position):
                    return False
                batch, size = [], 0
            batch.append(event)
            size += cost
            position = line.after
        if batch and not self._flush(batch, position):
            return False
        if position != saved:
            self._save(position)
        return True

    def start(self, interval: float = INTERVAL_SECONDS) -> None:
        def loop():
            while not self._stop.wait(interval):
                try:
                    self.poll()
                except Exception:
                    self.failures += 1

        self._thread = threading.Thread(target=loop, name="event-log-shipper", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
        close = getattr(self.client, "close", None)
        if close is not None:
            try:
                close()
            except Exception:
                self.failures += 1

    # -- sending ----------------------------------------------------------------------

    def _sendable(self, line: _Line, now_ms: int) -> bool:
        if line.timestamp is None:
            return False
        if (
            line.timestamp < now_ms - OLDEST_MS
            or line.timestamp > now_ms + NEWEST_MS
            or len(line.text.encode()) > EVENT_BYTES
        ):
            self.dropped += 1  # CloudWatch would refuse it; skip rather than block
            return False
        return True

    def _flush(self, batch, position: Position) -> bool:
        """Send one batch; on success or permanent refusal, save the checkpoint."""
        outcome = self._send(sorted(batch, key=lambda event: event["timestamp"]))
        if outcome == "retry":
            self.failures += 1
            return False
        if outcome == "refused":
            self.dropped += len(batch)
        last = max(event["timestamp"] for event in batch)
        self._save(_with_last(position, last))
        return True

    def _send(self, batch) -> str:
        errors = self.client.exceptions
        refused = tuple(
            getattr(errors, name)
            for name in ("InvalidParameterException", "DataAlreadyAcceptedException")
            if hasattr(errors, name)
        )
        for attempt in range(2):
            try:
                reply = self.client.put_log_events(
                    logGroupName=self.group, logStreamName=self.stream, logEvents=batch
                )
            except errors.ResourceNotFoundException:
                if attempt or not self._create_stream():
                    return "retry"
                continue
            except refused:
                return "refused"
            except Exception:
                return "retry"  # network trouble, throttling: the next poll tries again
            rejected = (reply or {}).get("rejectedLogEventsInfo")
            if rejected:
                self.dropped += 1
            return "sent"
        return "retry"

    def _create_stream(self) -> bool:
        try:
            self.client.create_log_stream(logGroupName=self.group, logStreamName=self.stream)
        except self.client.exceptions.ResourceAlreadyExistsException:
            pass
        except Exception:
            return False
        return True

    # -- reading ----------------------------------------------------------------------

    def _lines(self, saved: Position):
        """Unsent complete lines, oldest file first, each with the position after it."""
        files = [entry for entry in (self._read(name) for name in reversed(NAMES)) if entry]
        start = next(
            (i for i, (info, data) in enumerate(files) if _same_file(saved, info, data)), None
        )
        for index, (info, data) in enumerate(files):
            if start is not None and index < start:
                continue
            offset = saved.offset if index == start and saved.offset <= len(data) else 0
            # Without a trusted resume point, skip what was already sent by its time.
            skip_through = saved.last_ms if start is None or offset == 0 else -1
            last_ms = saved.last_ms
            head = _head(data)
            complete = data[: data.rfind(b"\n") + 1]
            for raw in complete[offset:].splitlines(keepends=True):
                offset += len(raw)
                text = raw.decode("ascii", "replace").rstrip("\n")
                timestamp = _timestamp(text)
                if timestamp is not None and timestamp <= skip_through:
                    timestamp = None
                if timestamp is not None:
                    last_ms = max(last_ms, timestamp)
                after = Position(info.st_dev, info.st_ino, head, offset, last_ms)
                yield _Line(timestamp, text, after)

    def _read(self, name):
        """(stat, bytes) of one managed log file, or None if it is absent."""
        if os.name != "posix":
            path = self.directory / name
            try:
                return path.stat(), path.read_bytes()
            except FileNotFoundError:
                return None
        from deploy.host_diagnostics import _directory

        folder = _directory(self.directory)
        try:
            return _read_private(folder, name, FILE_BYTES)
        except FileNotFoundError:
            return None
        finally:
            os.close(folder)

    # -- checkpoint -------------------------------------------------------------------

    def _load(self) -> Position:
        try:
            if os.name == "posix":
                from deploy.host_diagnostics import _directory

                folder = _directory(self.checkpoint.parent)
                try:
                    _, data = _read_private(folder, self.checkpoint.name, 4096)
                finally:
                    os.close(folder)
            else:
                data = self.checkpoint.read_bytes()
            value = json.loads(data)
            return Position(
                device=_integer(value.get("device")),
                inode=_integer(value.get("inode")),
                head=value.get("head") if isinstance(value.get("head"), str) else None,
                offset=_integer(value.get("offset")) or 0,
                last_ms=_integer(value.get("last_ms"), -1),
            )
        except (OSError, ValueError, AttributeError):
            return Position()

    def _save(self, position: Position) -> None:
        encoded = json.dumps(asdict(position)).encode()
        if os.name != "posix":
            temporary = self.checkpoint.with_name(self.checkpoint.name + ".tmp")
            temporary.write_bytes(encoded)
            os.replace(temporary, self.checkpoint)
            return
        from deploy.host_diagnostics import _directory

        folder = _directory(self.checkpoint.parent)
        temporary = f".{self.checkpoint.name}.{os.getpid()}.tmp"
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
            descriptor = os.open(temporary, flags, 0o600, dir_fd=folder)
            try:
                if os.write(descriptor, encoded) != len(encoded):
                    raise OSError("Incomplete checkpoint write")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.replace(temporary, self.checkpoint.name, src_dir_fd=folder, dst_dir_fd=folder)
            os.fsync(folder)
        except BaseException:
            with suppress(OSError):
                os.unlink(temporary, dir_fd=folder)
            raise
        finally:
            os.close(folder)


def _read_private(folder: int, name: str, limit: int):
    """Read a private file through the folder descriptor, refusing anything unsafe."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    descriptor = os.open(name, flags, dir_fd=folder)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or info.st_mode & 0o077
            or info.st_size > limit
        ):
            raise ValueError("Private bounded log file required")
        chunks, remaining = [], info.st_size
        while remaining > 0:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return info, b"".join(chunks)
    finally:
        os.close(descriptor)


def _head(data: bytes) -> str:
    """A short fingerprint of a file's first line, so a reused file number is detected."""
    first = data[: data.find(b"\n") + 1] if b"\n" in data else b""
    return hashlib.sha256(first).hexdigest()[:16]


def _same_file(saved: Position, info, data: bytes) -> bool:
    return (
        saved.inode is not None
        and saved.inode == info.st_ino
        and saved.device == info.st_dev
        and saved.head == _head(data)
        and saved.offset <= len(data)
    )


def _with_last(position: Position, last_ms: int) -> Position:
    return Position(
        position.device,
        position.inode,
        position.head,
        position.offset,
        max(position.last_ms, last_ms),
    )


def _integer(value, default=None):
    return value if type(value) is int else default


def _timestamp(text):
    """Milliseconds since the epoch for an ordinary record; None for debug or unreadable lines."""
    try:
        record = json.loads(text)
        if record.get("debug") is True or record.get("event") == "debug":
            return None
        return int(datetime.fromisoformat(record["time"]).timestamp() * 1000)
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
