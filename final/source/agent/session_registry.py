"""Session lookup, expiry, browser-tab ownership and write-through saving to the State Store."""

import hashlib
import json
from collections.abc import Callable
from time import monotonic, time
from uuid import uuid4

from agent import session_codec
from agent.session_state import LeaseConflict, Session, SessionExpired, SessionNotFound
from agent.state_store import (
    RevisionConflict,
    StateStore,
    StateStoreError,
)

# A Session expires this long after the Shopper's last activity (it was 30 minutes in memory).
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
# With a State Store, an idle Session leaves memory (capacity counts active Sessions) after this
# long; it is loaded again from the store when the Shopper comes back.
MEMORY_IDLE_SECONDS = 30 * 60
# Idle-but-unchanged Sessions refresh their stored expiry at most this often.
EXPIRY_REFRESH_SECONDS = 60 * 60
_IN_PROGRESS = {"interpreting", "awaiting_action_result"}


class StateSaveFailed(Exception):
    """A change could not be saved; the request that made it must fail visibly."""


def _key(session_id: str) -> str:
    return f"agent#session#{session_id}"


class SessionRegistry:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        capacity: int = 800,
        store: StateStore | None = None,
        wall_clock: Callable[[], float] = time,
        on_restore: Callable[[Session], None] | None = None,
    ) -> None:
        self._clock = clock
        self._wall_clock = wall_clock
        self._capacity = capacity
        self._store = store
        self._on_restore = on_restore
        self._sessions: dict[str, Session] = {}
        self._expired_ids: dict[str, float] = {}
        # Per stored Session: the revision we last wrote, the digest of what we wrote, and when.
        self._revisions: dict[str, int | None] = {}
        self._digests: dict[str, str] = {}
        self._saved_at: dict[str, float] = {}
        self._dirty: set[str] = set()
        # The value saved at the end of the last request (None: never saved), and the Sessions
        # saved mid-request since then; a failed request puts the baseline back.
        self._baseline: dict[str, dict | None] = {}
        self._checkpointed: set[str] = set()

    @property
    def _memory_seconds(self) -> float:
        return SESSION_TTL_SECONDS if self._store is None else MEMORY_IDLE_SECONDS

    def _expire(self) -> None:
        now = self._clock()
        for key, session in list(self._sessions.items()):
            if now - session.last_activity_at <= self._memory_seconds:
                continue
            if self._store is not None:
                # Saved already (write-through); work in progress stays in memory.
                if self._in_progress(session) or key in self._dirty:
                    continue
                self._forget(key)
            else:
                del self._sessions[key]
                self._expired_ids[key] = now
        for key, expired_at in list(self._expired_ids.items()):
            if now - expired_at > SESSION_TTL_SECONDS:
                del self._expired_ids[key]
        while len(self._expired_ids) > self._capacity:
            del self._expired_ids[next(iter(self._expired_ids))]

    @staticmethod
    def _in_progress(session: Session) -> bool:
        task = session.active_task
        return task is not None and task.status in _IN_PROGRESS

    def _forget(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._revisions.pop(session_id, None)
        self._digests.pop(session_id, None)
        self._saved_at.pop(session_id, None)
        self._baseline.pop(session_id, None)
        self._checkpointed.discard(session_id)

    def create(self, tab_id: str | None = None) -> Session:
        self._expire()
        if len(self._sessions) >= self._capacity:
            raise OverflowError("Session capacity reached")
        session = Session(
            session_id=f"session-{uuid4().hex}",
            lease_tab_id=tab_id,
            last_activity_at=self._clock(),
        )
        self._sessions[session.session_id] = session
        self._revisions[session.session_id] = None
        self._dirty.add(session.session_id)
        return session

    def has_capacity(self) -> bool:
        self._expire()
        return len(self._sessions) < self._capacity

    def has_pending_work(self) -> bool:
        self._expire()
        return any(self._in_progress(session) for session in self._sessions.values())

    def get(self, session_id: str) -> Session:
        self._expire()
        if session_id in self._expired_ids:
            raise SessionExpired(session_id)
        session = self._sessions.get(session_id)
        if session is None:
            session = self._load(session_id)
        # Whoever fetches a Session may change it: it is saved before the response goes out.
        self._dirty.add(session_id)
        return session

    def _load(self, session_id: str) -> Session:
        if self._store is None:
            raise SessionNotFound(session_id)
        try:
            record = self._store.read(_key(session_id))
        except StateStoreError as error:
            raise StateSaveFailed("The session could not be read") from error
        if record is None:
            raise SessionNotFound(session_id)
        session = session_codec.session_from_json(record.value, now=self._clock())
        self._sessions[session_id] = session
        self._revisions[session_id] = record.revision
        self._baseline[session_id] = record.value
        self._digests[session_id] = _digest(record.value)
        self._saved_at[session_id] = self._wall_clock()
        if self._on_restore is not None:
            self._on_restore(session)
        return session

    def touch(self, session: Session) -> None:
        session.last_activity_at = self._clock()

    def assert_lease(self, session: Session, tab_id: str | None) -> None:
        if session.lease_tab_id is None:
            if tab_id is not None:
                session.lease_tab_id = tab_id
            return
        if tab_id != session.lease_tab_id:
            raise LeaseConflict("Another browser tab owns this Shopping Task")

    def takeover(self, session_id: str, tab_id: str) -> Session:
        session = self.get(session_id)
        session.lease_tab_id = tab_id
        self.touch(session)
        return session

    def owns_lease(self, session_id: str, tab_id: str | None) -> bool:
        session = self.get(session_id)
        return session.lease_tab_id is None or session.lease_tab_id == tab_id

    def flush(self, *, checkpoint: bool = False) -> None:
        """Save every changed Session; raises `StateSaveFailed` if any save did not happen.

        A `checkpoint` is a save in the middle of a request (before work that must not start
        unless the change is kept); only the request's final flush ends the request's change.

        A Session that could not be saved is rolled back to its last saved state.
        """
        if self._store is None:
            self._dirty.clear()
            return
        failure: Exception | None = None
        for session_id in list(self._dirty):
            self._dirty.discard(session_id)
            session = self._sessions.get(session_id)
            if session is None:
                continue
            try:
                value = self._save(session)
            except (StateStoreError, RevisionConflict) as error:
                # The change is not saved, so it did not happen: put the last saved state of
                # the previous request back and drop the Session from memory; the next access
                # loads it (a never-saved one is gone).
                self._undo(session_id)
                self._forget(session_id)
                failure = error
                continue
            if checkpoint:
                self._checkpointed.add(session_id)
            else:
                self._baseline[session_id] = value
                self._checkpointed.discard(session_id)
        if failure is not None:
            raise StateSaveFailed("The change could not be saved") from failure

    def _undo(self, session_id: str) -> None:
        """Best effort: undo what this request already saved at a checkpoint."""
        if self._store is None or session_id not in self._checkpointed:
            return
        key = _key(session_id)
        try:
            current = self._store.read(key)
            baseline = self._baseline.get(session_id)
            if current is None:
                return
            if baseline is None:
                self._store.delete(key)
            else:
                expires_at = self._wall_clock() + SESSION_TTL_SECONDS
                self._store.write(key, baseline, expires_at, current.revision)
        except (StateStoreError, RevisionConflict):
            pass  # the checkpointed state stays: consistent, and restored as interrupted

    def _save(self, session: Session) -> dict:
        assert self._store is not None
        session_id = session.session_id
        value = session_codec.session_to_json(session)
        digest = _digest(value)
        now = self._wall_clock()
        stale = now - self._saved_at.get(session_id, 0.0) > EXPIRY_REFRESH_SECONDS
        if digest == self._digests.get(session_id) and not stale:
            return value
        key, expires_at = _key(session_id), now + SESSION_TTL_SECONDS
        try:
            revision = self._store.write(key, value, expires_at, self._revisions.get(session_id))
        except RevisionConflict:
            # Another writer saved this Session meanwhile: reload its revision and retry once.
            current = self._store.read(key)
            revision = self._store.write(
                key, value, expires_at, current.revision if current is not None else None
            )
        self._revisions[session_id] = revision
        self._digests[session_id] = digest
        self._saved_at[session_id] = now
        return value


def _digest(value: dict) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
