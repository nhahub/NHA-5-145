"""Durable generation, admission and stop arbitration outside the simulated host."""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from time import time
from uuid import uuid4

IDLE_SECONDS = 3600
WORK_LEASE_SECONDS = 45
START_DEADLINE_SECONDS = 300
START_GRACE_SECONDS = 120
COOLDOWN_SECONDS = 60
DRAIN_SECONDS = 5


class LifecycleUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("Demo is starting, stopping or unavailable; return to the waiting page")


class Lifecycle:
    @staticmethod
    def initialize(path: Path) -> str:
        path = Path(path).resolve()
        path.touch(mode=0o600, exist_ok=False)
        identity = str(uuid4())
        with closing(sqlite3.connect(path)) as db:
            db.executescript("""
                PRAGMA synchronous=FULL;
                CREATE TABLE policy(version INTEGER, identity TEXT);
                CREATE TABLE host(
                    state TEXT, generation INTEGER, activity REAL, deadline REAL,
                    changed REAL, observed REAL, invitation TEXT, commanded INTEGER,
                    grace REAL, attempts INTEGER, retry REAL, recoverable INTEGER
                );
                INSERT INTO host VALUES('stopped',0,0,0,0,0,NULL,0,0,0,0,1);
                CREATE TABLE work(token TEXT PRIMARY KEY, generation INTEGER, expires REAL);
                CREATE TABLE rate(kind TEXT PRIMARY KEY, minute INTEGER, count INTEGER);
            """)
            db.execute("INSERT INTO policy VALUES(1,?)", (identity,))
            db.commit()
        return identity

    def __init__(self, path, identity, invitations, *, clock=time):
        self.path, self.identity = Path(path).resolve(), identity
        self.invitations, self.clock = invitations, clock
        with self._transaction():
            pass

    @contextmanager
    def _transaction(self):
        db = None
        try:
            db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=1)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA synchronous=FULL")
            if db.execute("PRAGMA max_page_count=1024").fetchone()[0] > 1024:
                raise LifecycleUnavailable()
            db.execute("BEGIN IMMEDIATE")
            if tuple(db.execute("PRAGMA quick_check").fetchone()) != ("ok",) or [
                tuple(row) for row in db.execute("SELECT * FROM policy")
            ] != [(1, self.identity)]:
                raise LifecycleUnavailable()
            host = dict(db.execute("SELECT * FROM host").fetchone())
            now = self.clock()
            if now < host["observed"]:
                raise LifecycleUnavailable()
            db.execute("UPDATE host SET observed=?", (now,))
            db.execute("DELETE FROM work WHERE expires<?", (now,))
            yield db, host, now
            db.commit()
        except (sqlite3.Error, TypeError, ValueError) as error:
            raise LifecycleUnavailable() from error
        finally:
            if db is not None:
                db.close()

    @staticmethod
    def _view(host, now):
        return {
            "state": host["state"],
            "generation": host["generation"],
            "remaining_seconds": max(0, int(host["deadline"] - now))
            if host["state"] == "starting"
            else 0,
            "retry_after": COOLDOWN_SECONDS if host["state"] == "failed" else 5,
        }

    def status(self):
        with self._transaction() as (_, host, now):
            return self._view(host, now)

    def rate(self, kind, maximum):
        """Fixed cardinality counters survive waiting-service restarts."""
        if kind not in {"http", "wake", "poll"}:
            raise ValueError("Unknown rate lane")
        with self._transaction() as (db, _, now):
            minute = int(now // 60)
            db.execute(
                "INSERT INTO rate VALUES(?,?,1) ON CONFLICT(kind) DO UPDATE SET "
                "count=CASE WHEN minute=excluded.minute THEN count+1 ELSE 1 END, "
                "minute=excluded.minute",
                (kind, minute),
            )
            count = db.execute("SELECT count FROM rate WHERE kind=?", (kind,)).fetchone()[0]
        if count > maximum:
            raise LifecycleUnavailable()

    def wake(self, code):
        invitation = self.invitations.wake_invitation(code)
        return self._start(invitation)

    def manual_start(self):
        """Owner-only Python interface; no public manual bypass endpoint."""
        return self._start(None)

    def _start(self, invitation):
        with self._transaction() as (db, host, now):
            if host["state"] == "failed" and (
                now - host["changed"] < COOLDOWN_SECONDS or not host["recoverable"]
            ):
                raise LifecycleUnavailable()
            if host["state"] in {"stopped", "failed"}:
                host.update(
                    state="starting",
                    generation=host["generation"] + 1,
                    activity=now,
                    deadline=now + START_DEADLINE_SECONDS,
                    changed=now,
                    invitation=invitation,
                    commanded=0,
                    attempts=0,
                    retry=0,
                    recoverable=0,
                )
                db.execute("DELETE FROM work")
                self._save(db, host)
            # Arrival after stop commitment must wait, never cancel committed stop.
            return self._view(host, now)

    @staticmethod
    def _save(db, host):
        db.execute(
            "UPDATE host SET state=:state,generation=:generation,activity=:activity,"
            "deadline=:deadline,changed=:changed,invitation=:invitation,commanded=:commanded,"
            "grace=:grace,attempts=:attempts,retry=:retry,recoverable=:recoverable",
            host,
        )

    def begin_work(self, *, meaningful=False, generation=None):
        with self._transaction() as (db, host, now):
            if host["state"] not in {"ready", "draining"} or (
                generation is not None and generation != host["generation"]
            ):
                raise LifecycleUnavailable()
            if db.execute("SELECT COUNT(*) FROM work").fetchone()[0] >= 128:
                raise LifecycleUnavailable()
            if meaningful:
                host.update(state="ready", activity=now, changed=now)
                self._save(db, host)
            token = uuid4().hex
            db.execute(
                "INSERT INTO work VALUES(?,?,?)",
                (token, host["generation"], now + WORK_LEASE_SECONDS),
            )
            return token

    def renew_work(self, token):
        with self._transaction() as (db, host, now):
            if (
                host["state"] not in {"ready", "draining", "unhealthy"}
                or db.execute(
                    "UPDATE work SET expires=? WHERE token=? AND generation=? AND expires>=?",
                    (now + WORK_LEASE_SECONDS, token, host["generation"], now),
                ).rowcount
                != 1
            ):
                raise LifecycleUnavailable()

    def end_work(self, token):
        with self._transaction() as (db, _, _now):
            db.execute("DELETE FROM work WHERE token=?", (token,))

    def tick(self, control):
        """One bounded reconciliation, never waits for boot; repeat after crashes.

        The adapter controls one fixed host; start/stop must be idempotent for a
        generation and return promptly. Commands are serialized with admission.
        A real AWS adapter/transport is deliberately not included here.
        """
        generation = self.status()["generation"]
        # Observation may involve slow health/network I/O. Never hold the writer
        # lock while it runs: accepted work must be able to renew its lease.
        try:
            state, healthy = control.observe()
        except Exception:
            state, healthy = "unknown", False
        with self._transaction() as (db, host, now):
            if host["generation"] != generation:
                return self._view(host, now)
            if host["state"] == "starting":
                if now >= host["deadline"]:
                    host.update(state="failed", changed=now, commanded=0, attempts=0, retry=0)
                    self._command(control, "stop", host, now)
                elif not host["commanded"]:
                    if host["invitation"] and not self.invitations.valid_invitation(
                        host["invitation"]
                    ):
                        host.update(
                            state="failed", changed=now, recoverable=int(state == "stopped")
                        )
                    else:
                        self._command(control, "start", host, now)
                elif state == "running" and healthy:
                    host.update(
                        state="ready", activity=now, changed=now, grace=now + START_GRACE_SECONDS
                    )
            elif host["state"] in {"ready", "draining", "unhealthy"}:
                busy = db.execute("SELECT COUNT(*) FROM work").fetchone()[0] > 0
                idle = now - host["activity"] >= IDLE_SECONDS
                if state == "stopped":
                    host.update(state="stopped", changed=now)
                    db.execute("DELETE FROM work")
                elif busy or not idle or now < host["grace"]:
                    desired = "ready" if healthy else "unhealthy"
                    if host["state"] != desired:
                        host.update(state=desired, changed=now)
                elif host["state"] != "draining":
                    host.update(state="draining", changed=now)
                elif now - host["changed"] >= DRAIN_SECONDS:
                    host.update(state="stopping", changed=now, commanded=0, attempts=0, retry=0)
            elif host["state"] == "stopping":
                # Stop intent was committed before invoking the external control.
                if state == "stopped":
                    host.update(state="stopped", changed=now)
                elif now - host["changed"] >= 120:
                    host.update(state="failed", changed=now, recoverable=0)
                else:
                    self._command(control, "stop", host, now)
            elif host["state"] == "failed":
                if state == "stopped":
                    host["recoverable"] = 1
                elif not host["recoverable"]:
                    self._command(control, "stop", host, now)
            self._save(db, host)
            return self._view(host, now)

    @staticmethod
    def _command(control, operation, host, now):
        if host["commanded"] or host["attempts"] >= 3 or now < host["retry"]:
            return
        host["attempts"] += 1
        try:
            getattr(control, operation)(host["generation"])
            host["commanded"] = 1
        except Exception:
            host["retry"] = now + 10
            if host["attempts"] >= 3:
                host.update(state="failed", changed=now, recoverable=0)
                if operation == "start":
                    # An uncertain start needs bounded stop cleanup, not another
                    # boot generation. New starts require observed stopped state.
                    host.update(attempts=0, commanded=0, retry=now + 10)
