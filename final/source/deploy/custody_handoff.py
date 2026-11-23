"""CAP-07 operator-only, disabled-destination custody handoff; no network or key reads."""

import hashlib
import json
import os
import sqlite3
import stat
import tempfile
from contextlib import closing
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from uuid import UUID

SCALE = Decimal(1_000_000_000)
SOURCE_COUNT, IMPORT_COUNT = 156, 72
SOURCE_CHARGED, IMPORT_CHARGED = 199682910, 95010110
HELD, RESERVE, CAP = 255886201, 100000000, 2000000000
REFUSAL = "Custody handoff refused"


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _safe(path, limit):
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError()
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise ValueError()
    info = path.stat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or not 0 < info.st_size <= limit
        or os.name == "posix"
        and (info.st_uid not in {0, os.geteuid()} or info.st_mode & 0o077)
    ):
        raise ValueError()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _amount(value):
    if type(value) is not str:
        raise ValueError()
    amount = Decimal(value)
    if not amount.is_finite() or not 0 <= amount <= 2:
        raise ValueError()
    return int((amount * SCALE).to_integral_value(rounding=ROUND_CEILING))


def _db(path):
    if any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError()
        objects = db.execute(
            "SELECT type,name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()
        if set(objects) != {("table", "policy"), ("table", "attempts")}:
            raise ValueError()
        policy = db.execute("SELECT version,identity,allowance,enabled FROM policy").fetchall()
        attempts = db.execute(
            "SELECT id,reservation,charged,settled FROM attempts ORDER BY id LIMIT 513"
        ).fetchall()
    if (
        len(policy) != 1
        or policy[0][0] != 1
        or str(UUID(policy[0][1])) != policy[0][1]
        or type(policy[0][2]) is not int
        or not 0 < policy[0][2] <= CAP
        or policy[0][3] != 0
        or len(attempts) > 512
    ):
        raise ValueError()
    result = {}
    for identifier, reservation, charged, settled in attempts:
        if (
            type(identifier) is not str
            or not 0 < len(identifier) <= 200
            or identifier in result
            or any(type(number) is not int for number in (reservation, charged, settled))
            or not 0 < reservation <= CAP
            or not 0 <= charged <= CAP
            or settled not in {0, 1}
            or not settled
            and charged != reservation
        ):
            raise ValueError()
        result[identifier] = (reservation, charged, settled)
    return policy[0], result


def prepare_handoff(source: Path, manifest: Path, destination: Path) -> dict:
    """Preserve the shared UUID/history and add the approved bounded reserve, disabled.

    Caller must quiesce/disable all writers and independently verify actual Windows
    custody ACLs. Inputs are consistent disabled SQLite backups, never active DBs.
    Output is private operator evidence; its file digest must not enter public logs.
    """
    temporary = None
    try:
        _safe(manifest, 65536)
        data = json.loads(manifest.read_bytes(), object_pairs_hook=_pairs)
        if (
            set(data)
            != {"version", "source_sha256", "imports", "holds", "provider_status", "readiness_usd"}
            or type(data["version"]) is not int
            or data["version"] != 1
            or _amount(data["readiness_usd"]) != RESERVE
            or type(data["imports"]) is not list
            or len(data["imports"]) != 1
            or type(data["holds"]) is not list
            or len(data["holds"]) != 19
        ):
            raise ValueError()
        original_hash = _safe(source, 4194304)
        if original_hash != data["source_sha256"]:
            raise ValueError()
        policy, original = _db(source)
        if (
            len(original) != SOURCE_COUNT
            or sum(row[1] for row in original.values()) != SOURCE_CHARGED
            or any(row[2] != 1 for row in original.values())
        ):
            raise ValueError()
        entry = data["imports"][0]
        if set(entry) != {"path", "sha256"}:
            raise ValueError()
        other = Path(entry["path"])
        if other.resolve() == source.resolve() or _safe(other, 4194304) != entry["sha256"]:
            raise ValueError()
        other_policy, imported = _db(other)
        if (
            len(imported) != IMPORT_COUNT
            or sum(row[1] for row in imported.values()) != IMPORT_CHARGED
            or any(row[2] != 1 for row in imported.values())
            or other_policy[1] == policy[1]
        ):
            raise ValueError()
        combined = dict(original)
        for identifier, row in imported.items():
            if identifier in combined:
                raise ValueError()
            combined[identifier] = row
        for hold in data["holds"]:
            if set(hold) != {"id", "reservation", "evidence_sha256"}:
                raise ValueError()
            identifier, amount = hold["id"], hold["reservation"]
            evidence = hold["evidence_sha256"]
            if (
                type(identifier) is not str
                or not 0 < len(identifier) <= 200
                or identifier in combined
                or type(amount) is not int
                or not 0 < amount <= HELD
                or type(evidence) is not str
                or len(evidence) != 64
                or any(c not in "0123456789abcdef" for c in evidence)
            ):
                raise ValueError()
            combined[identifier] = (amount, amount, 0)
        held = sum(row[1] for row in combined.values() if not row[2])
        status = data["provider_status"]
        if (
            held != HELD
            or set(status) != {"limit_usd", "remaining_usd", "usage_usd", "limit_reset"}
            or _amount(status["limit_usd"]) != CAP
            or status["limit_reset"] is not None
            or _amount(status["remaining_usd"]) < held + RESERVE
        ):
            raise ValueError()
        usage = _amount(status["usage_usd"])
        gap = max(0, usage - SOURCE_CHARGED - IMPORT_CHARGED)
        if gap:
            combined["cap07-provider-aggregate-gap"] = (gap, gap, 0)
        accounted = sum(row[1] for row in combined.values())
        allowance = accounted + RESERVE
        if allowance > CAP:
            raise ValueError()
        if (
            not destination.is_absolute()
            or destination.resolve() in {source.resolve(), other.resolve(), manifest.resolve()}
            or not destination.parent.is_dir()
            or any(p.is_symlink() for p in (destination, *destination.parents))
        ):
            raise ValueError()
        expected = (1, policy[1], allowance, 0)
        exists = destination.exists()
        if exists:
            _safe(destination, 4194304)
            actual_policy, actual_rows = _db(destination)
            if actual_policy != expected or actual_rows != combined:
                raise ValueError()
        else:
            descriptor, name = tempfile.mkstemp(prefix=".cap07-", dir=destination.parent)
            os.close(descriptor)
            temporary = Path(name)
            temporary.chmod(0o600)
            with (
                closing(sqlite3.connect(source.as_uri() + "?mode=ro&immutable=1", uri=True)) as src,
                closing(sqlite3.connect(temporary)) as dst,
            ):
                src.backup(dst)
                with dst:
                    dst.execute("PRAGMA synchronous=FULL")
                    for identifier, row in combined.items():
                        if identifier not in original:
                            dst.execute("INSERT INTO attempts VALUES(?,?,?,?)", (identifier, *row))
                    dst.execute("UPDATE policy SET allowance=?,enabled=0", (allowance,))
            if _db(temporary) != (expected, combined):
                raise ValueError()
            if _safe(source, 4194304) != original_hash or _safe(other, 4194304) != entry["sha256"]:
                raise ValueError()
            # No overwrite of an existing destination, including a competing writer.
            if destination.exists():
                raise ValueError()
            os.replace(temporary, destination)
            temporary = None
        return {
            "already_prepared": exists,
            "enabled": False,
            "settled_attempts": SOURCE_COUNT + IMPORT_COUNT,
            "legacy_holds": 19,
            "provider_gap_hold": bool(gap),
            "accounted_usd": f"{Decimal(accounted) / SCALE:.9f}",
            "allowance_usd": f"{Decimal(allowance) / SCALE:.9f}",
            "remaining_usd": "0.100000000",
            "ledger_sha256": _safe(destination, 4194304),
        }
    except Exception:
        raise ValueError(REFUSAL) from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
