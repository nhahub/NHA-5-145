"""Durable invitation windows and quotas. No raw access code is stored."""

import hashlib
import secrets
import sqlite3
from collections.abc import Callable
from contextlib import closing, contextmanager
from math import isfinite
from pathlib import Path
from time import time
from uuid import uuid4


class AdmissionDenied(RuntimeError):
    def __init__(self, reason="access_required"):
        self.reason = reason
        super().__init__("Demo access unavailable")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class InvitationStore:
    @staticmethod
    def initialize(path: Path) -> str:
        path = Path(path).resolve()
        path.touch(mode=0o600, exist_ok=False)
        identity = str(uuid4())
        with closing(sqlite3.connect(path)) as db:
            db.executescript("""
                PRAGMA synchronous=FULL;
                CREATE TABLE policy(version INTEGER, identity TEXT);
                CREATE TABLE invitations(
                    id TEXT PRIMARY KEY, hash TEXT UNIQUE NOT NULL,
                    starts REAL NOT NULL, ends REAL NOT NULL,
                    redemptions INTEGER NOT NULL, sessions INTEGER NOT NULL,
                    created_sessions INTEGER NOT NULL DEFAULT 0, revoked INTEGER NOT NULL DEFAULT 0,
                    used_redemptions INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE grants(subject TEXT PRIMARY KEY, invitation TEXT NOT NULL);
            """)
            db.execute("INSERT INTO policy VALUES(1,?)", (identity,))
            db.commit()
        return identity

    def __init__(self, path: Path, identity: str, *, clock: Callable[[], float] = time):
        self.path, self.identity, self.clock = Path(path).resolve(), identity, clock
        with self._transaction():
            pass

    @contextmanager
    def _transaction(self):
        db = None
        try:
            db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=1)
            db.execute("PRAGMA synchronous=FULL")
            if db.execute("PRAGMA max_page_count=1024").fetchone()[0] > 1024:
                raise AdmissionDenied("access_unavailable")
            db.execute("BEGIN IMMEDIATE")
            if db.execute("PRAGMA quick_check").fetchone() != ("ok",) or db.execute(
                "SELECT version,identity FROM policy"
            ).fetchall() != [(1, self.identity)]:
                raise AdmissionDenied("access_unavailable")
            yield db
            db.commit()
        except sqlite3.Error as error:
            raise AdmissionDenied("access_unavailable") from error
        finally:
            if db is not None:
                db.close()

    def issue(self, starts: float, ends: float, *, redemptions: int, sessions: int):
        if (
            not all(isinstance(x, int | float) and isfinite(x) for x in (starts, ends))
            or not 0 <= starts < ends
            or ends - starts > 31 * 86400
            or type(redemptions) is not int
            or not 1 <= redemptions <= 20
            or type(sessions) is not int
            or not 1 <= sessions <= 100
        ):
            raise ValueError("Explicit finite invitation window and quotas are required")
        invitation, code = str(uuid4()), secrets.token_urlsafe(24)
        with self._transaction() as db:
            if db.execute("SELECT COUNT(*) FROM invitations").fetchone()[0] >= 1000:
                raise AdmissionDenied("access_capacity")
            db.execute(
                "INSERT INTO invitations(id,hash,starts,ends,redemptions,sessions) "
                "VALUES(?,?,?,?,?,?)",
                (invitation, digest(code), starts, ends, redemptions, sessions),
            )
        return invitation, code

    def redeem(self, code: str, subject: str) -> None:
        if not isinstance(code, str) or not 16 <= len(code) <= 128 or len(subject) > 256:
            raise AdmissionDenied()
        with self._transaction() as db:
            row = db.execute(
                "SELECT id,starts,ends,redemptions,revoked FROM invitations WHERE hash=?",
                (digest(code),),
            ).fetchone()
            now = self.clock()
            if not row or row[4] or not row[1] <= now < row[2]:
                raise AdmissionDenied()
            existing = db.execute(
                "SELECT invitation FROM grants WHERE subject=?", (digest(subject),)
            ).fetchone()
            if existing:
                if existing[0] == row[0]:
                    return
                if self._valid_grant(db, subject):
                    raise AdmissionDenied()
            used = db.execute(
                "UPDATE invitations SET used_redemptions=used_redemptions+1 "
                "WHERE id=? AND used_redemptions<redemptions",
                (row[0],),
            )
            if used.rowcount != 1:
                raise AdmissionDenied()
            db.execute("INSERT OR REPLACE INTO grants VALUES(?,?)", (digest(subject), row[0]))

    def wake_invitation(self, code: str) -> str:
        """Validate wake access without redeeming browser/application authority."""
        if not isinstance(code, str) or not 16 <= len(code) <= 128:
            raise AdmissionDenied()
        with self._transaction() as db:
            now = self.clock()
            row = db.execute(
                "SELECT id FROM invitations WHERE hash=? AND revoked=0 AND starts<=? AND ends>?",
                (digest(code), now, now),
            ).fetchone()
            if row is None:
                raise AdmissionDenied()
            return row[0]

    def valid_invitation(self, invitation: str) -> bool:
        with self._transaction() as db:
            now = self.clock()
            return (
                db.execute(
                    "SELECT 1 FROM invitations WHERE id=? AND revoked=0 AND starts<=? AND ends>?",
                    (invitation, now, now),
                ).fetchone()
                is not None
            )

    def _valid_grant(self, db, subject):
        now = self.clock()
        return db.execute(
            "SELECT i.id FROM grants g JOIN invitations i ON i.id=g.invitation "
            "WHERE g.subject=? AND i.revoked=0 AND i.starts<=? AND i.ends>?",
            (digest(subject), now, now),
        ).fetchone()

    def allowed(self, subject: str) -> bool:
        try:
            with self._transaction() as db:
                return self._valid_grant(db, subject) is not None
        except AdmissionDenied:
            return False

    def allocate_session(self, subject: str) -> str:
        """Count one new Shopping session against the grant; return its invitation id."""
        with self._transaction() as db:
            row = self._valid_grant(db, subject)
            if not row:
                raise AdmissionDenied()
            result = db.execute(
                "UPDATE invitations SET created_sessions=created_sessions+1 "
                "WHERE id=? AND created_sessions<sessions",
                (row[0],),
            )
            if result.rowcount != 1:
                raise AdmissionDenied("access_sessions")
            return row[0]

    def revoke(self, invitation: str) -> None:
        with self._transaction() as db:
            if (
                db.execute("UPDATE invitations SET revoked=1 WHERE id=?", (invitation,)).rowcount
                != 1
            ):
                raise ValueError("Invitation not found")

    def status(self) -> list[dict]:
        with self._transaction() as db:
            rows = db.execute(
                "SELECT id,starts,ends,redemptions,sessions,created_sessions,revoked,"
                "used_redemptions FROM invitations"
            ).fetchall()
            keys = (
                "id",
                "starts",
                "ends",
                "redemptions",
                "sessions",
                "used_sessions",
                "revoked",
                "used_redemptions",
            )
            return [dict(zip(keys, row, strict=True)) for row in rows]
