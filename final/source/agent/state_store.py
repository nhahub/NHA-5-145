"""Agent session State Store: a small key-value interface and its local SQLite-file adapter.

Values are JSON documents. A write names the revision it expects (optimistic concurrency) and
the record's expiry; an expired record reads as missing. Another adapter (DynamoDB) plugs into
the same contract: see `agent/tests/state_store_contract.py`.
"""

import json
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Any, Protocol

# DynamoDB refuses items near 400 KB; a record this size is refused long before that.
MAX_RECORD_BYTES = 256 * 1024


class StateStoreError(Exception):
    """The store could not read or write; the request must fail visibly."""


class RevisionConflict(StateStoreError):
    """The record changed (or exists, or is missing) since the revision the writer saw."""


class RecordTooLarge(StateStoreError):
    """The record exceeds the size guard and was not saved."""


@dataclass(frozen=True)
class StoredRecord:
    value: dict[str, Any]
    revision: int
    expires_at: float


class StateStore(Protocol):
    def read(self, key: str) -> StoredRecord | None:
        """The live record, or None when it is missing or expired."""

    def write(
        self,
        key: str,
        value: dict[str, Any],
        expires_at: float,
        expected_revision: int | None,
    ) -> int:
        """Save `value`; return the new revision (1 for a new record).

        `expected_revision` None means the record must not exist yet (an expired record counts
        as missing); otherwise it must be the live record's revision. A mismatch raises
        `RevisionConflict`; an oversized value raises `RecordTooLarge`.
        """

    def delete(self, key: str) -> None:
        """Remove the record; deleting a missing record is not an error."""


def encode_value(value: dict[str, Any]) -> str:
    """The JSON text of a record, refused when it is over the size guard."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(text.encode("utf-8")) > MAX_RECORD_BYTES:
        raise RecordTooLarge("The record is too large to save")
    return text


class SqliteStateStore:
    """One table in one local file; safe for several instances on the same file."""

    def __init__(self, path: str | Path, *, clock: Callable[[], float] = time) -> None:
        self._path = Path(path)
        self._clock = clock
        self._lock = threading.Lock()
        self._connection: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._connection is None:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(
                    self._path, timeout=10, isolation_level=None, check_same_thread=False
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS state ("
                    "key TEXT PRIMARY KEY, value TEXT NOT NULL, "
                    "revision INTEGER NOT NULL, expires_at REAL NOT NULL)"
                )
                connection.execute("DELETE FROM state WHERE expires_at <= ?", (self._clock(),))
            except (OSError, sqlite3.Error) as error:
                raise StateStoreError("The state file could not be opened") from error
            self._connection = connection
        return self._connection

    def read(self, key: str) -> StoredRecord | None:
        with self._lock:
            try:
                row = (
                    self._connect()
                    .execute("SELECT value, revision, expires_at FROM state WHERE key = ?", (key,))
                    .fetchone()
                )
                if row is None:
                    return None
                if row[2] <= self._clock():
                    self._connect().execute("DELETE FROM state WHERE key = ?", (key,))
                    return None
                return StoredRecord(json.loads(row[0]), int(row[1]), float(row[2]))
            except (sqlite3.Error, ValueError) as error:
                raise StateStoreError("The state could not be read") from error

    def write(
        self,
        key: str,
        value: dict[str, Any],
        expires_at: float,
        expected_revision: int | None,
    ) -> int:
        text = encode_value(value)
        with self._lock:
            try:
                connection = self._connect()
                connection.execute("BEGIN IMMEDIATE")
                try:
                    row = connection.execute(
                        "SELECT revision, expires_at FROM state WHERE key = ?", (key,)
                    ).fetchone()
                    live = row is not None and row[1] > self._clock()
                    current = int(row[0]) if live else None
                    if current != expected_revision:
                        raise RevisionConflict("The record changed since it was read")
                    revision = (current or 0) + 1
                    connection.execute(
                        "INSERT INTO state (key, value, revision, expires_at) VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                        "revision = excluded.revision, expires_at = excluded.expires_at",
                        (key, text, revision, expires_at),
                    )
                    connection.execute("COMMIT")
                    return revision
                except BaseException:
                    connection.execute("ROLLBACK")
                    raise
            except sqlite3.Error as error:
                raise StateStoreError("The state could not be saved") from error

    def delete(self, key: str) -> None:
        with self._lock:
            try:
                self._connect().execute("DELETE FROM state WHERE key = ?", (key,))
            except sqlite3.Error as error:
                raise StateStoreError("The state could not be deleted") from error

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None


def default_state_path() -> Path:
    return Path(__file__).resolve().parents[1] / "work" / "agent-state.sqlite"


def configured_state_store(values: Any) -> StateStore | None:
    """The store the Agent saves sessions in: a local file by default.

    `AGENT_STATE_FILE` picks another file; `AGENT_STATE_STORE=memory` keeps sessions in
    process memory only (the way a host without a writable disk runs).
    """
    if values.get("AGENT_STATE_STORE") == "memory":
        return None
    configured = values.get("AGENT_STATE_FILE")
    return SqliteStateStore(configured or default_state_path())
