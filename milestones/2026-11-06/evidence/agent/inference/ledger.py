"""Explicitly initialized allowance; opening runtime storage never creates it."""

import sqlite3
from contextlib import closing, contextmanager
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from uuid import uuid4

SCALE = Decimal(1_000_000_000)


class InferenceRefused(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def units(amount: Decimal) -> int:
    if not isinstance(amount, Decimal) or not amount.is_finite() or not 0 <= amount <= 1_000_000:
        raise ValueError("Invalid finite USD amount")
    return int((amount * SCALE).to_integral_value(rounding=ROUND_CEILING))


def dollars(value: int) -> str:
    return f"{Decimal(value) / SCALE:.9f}"


class AllowanceLedger:
    @staticmethod
    def initialize(path: Path, allowance: Decimal) -> str:
        limit = units(allowance)
        if limit <= 0:
            raise ValueError("Allowance must be positive")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=False)
        identity = str(uuid4())
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript(
                """
                PRAGMA journal_mode=DELETE;
                PRAGMA synchronous=FULL;
                CREATE TABLE policy (
                    version INTEGER NOT NULL CHECK(version=1),
                    identity TEXT NOT NULL PRIMARY KEY,
                    allowance INTEGER NOT NULL CHECK(allowance>0),
                    enabled INTEGER NOT NULL CHECK(enabled IN (0,1))
                );
                CREATE TABLE attempts (
                    id TEXT NOT NULL PRIMARY KEY,
                    reservation INTEGER NOT NULL CHECK(reservation>0),
                    charged INTEGER NOT NULL CHECK(charged>=0),
                    settled INTEGER NOT NULL CHECK(settled IN (0,1))
                );
                """
            )
            db.execute("INSERT INTO policy VALUES(1,?,?,1)", (identity, limit))
        return identity

    def __init__(self, path: Path, identity: str, *, maximum_pages: int = 1024):
        self.path, self.identity = Path(path).resolve(), identity
        if not identity or not isinstance(maximum_pages, int) or not 5 <= maximum_pages <= 262_144:
            raise ValueError("Ledger identity and finite storage bound are required")
        self.maximum_pages = maximum_pages
        self.status()

    @contextmanager
    def _transaction(self):
        db = None
        try:
            db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=1)
            db.execute("PRAGMA synchronous=FULL")
            maximum = db.execute(f"PRAGMA max_page_count={self.maximum_pages}").fetchone()[0]
            if maximum > self.maximum_pages:
                raise InferenceRefused("unavailable")
            db.execute("BEGIN IMMEDIATE")
            if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise InferenceRefused("unavailable")
            rows = db.execute("SELECT version,identity,allowance,enabled FROM policy").fetchall()
            if len(rows) != 1 or rows[0][:2] != (1, self.identity):
                raise InferenceRefused("unavailable")
            yield db, rows[0]
            db.commit()
        except sqlite3.Error as error:
            raise InferenceRefused("unavailable") from error
        finally:
            if db is not None:
                db.close()

    def status(self) -> dict:
        with self._transaction() as (db, policy):
            charged, count, pending = db.execute(
                "SELECT COALESCE(SUM(charged),0),COUNT(*),"
                "COALESCE(SUM(CASE WHEN settled=0 THEN 1 ELSE 0 END),0) FROM attempts"
            ).fetchone()
            return {
                "identity": policy[1],
                "enabled": bool(policy[3]),
                "allowance_usd": dollars(policy[2]),
                "accounted_usd": dollars(charged),
                "remaining_usd": dollars(max(0, policy[2] - charged)),
                "attempts": count,
                "uncertain": pending,
            }

    def reserve(
        self, attempt: str, amount: Decimal, *, maximum_attempts: int | None = None
    ) -> None:
        value = units(amount)
        if not isinstance(attempt, str) or not 0 < len(attempt) <= 200 or value <= 0:
            raise ValueError("Bounded attempt identity and positive reservation are required")
        if maximum_attempts is not None and (
            isinstance(maximum_attempts, bool)
            or not isinstance(maximum_attempts, int)
            or not 1 <= maximum_attempts <= 1_000_000
        ):
            raise ValueError("Attempt bound must be a positive finite integer")
        with self._transaction() as (db, policy):
            if not policy[3]:
                raise InferenceRefused("disabled")
            if db.execute("SELECT 1 FROM attempts WHERE id=?", (attempt,)).fetchone():
                raise InferenceRefused("duplicate")
            used = db.execute("SELECT COALESCE(SUM(charged),0) FROM attempts").fetchone()[0]
            if maximum_attempts is not None:
                count = db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
                if count >= maximum_attempts:
                    raise InferenceRefused("budget")
            if value > policy[2] - used:
                raise InferenceRefused("budget")
            db.execute("INSERT INTO attempts VALUES(?,?,?,0)", (attempt, value, value))

    def settle(self, attempt: str, amount: Decimal) -> None:
        cost = units(amount)
        exceeded = False
        with self._transaction() as (db, _policy):
            row = db.execute(
                "SELECT reservation,charged,settled FROM attempts WHERE id=?", (attempt,)
            ).fetchone()
            if row is None or (row[2] and cost != row[1]):
                raise InferenceRefused("duplicate")
            if row[2]:
                return
            db.execute("UPDATE attempts SET charged=?,settled=1 WHERE id=?", (cost, attempt))
            exceeded = cost > row[0]
            if exceeded:
                db.execute("UPDATE policy SET enabled=0")
        if exceeded:
            raise InferenceRefused("disabled")

    def ensure_accounted(self, attempt: str) -> None:
        with self._transaction() as (db, _policy):
            if not db.execute("SELECT 1 FROM attempts WHERE id=?", (attempt,)).fetchone():
                raise InferenceRefused("unavailable")

    def set_enabled(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("Kill switch must be boolean")
        with self._transaction() as (db, _policy):
            db.execute("UPDATE policy SET enabled=?", (int(enabled),))
