"""Synthetic custody only: no dotenv, network or existing operator databases."""

import hashlib
import json
import sqlite3
from decimal import Decimal

import pytest

from agent.inference.ledger import AllowanceLedger


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with sqlite3.connect(path) as db:
        return db.execute("SELECT * FROM attempts ORDER BY id").fetchall()


@pytest.fixture
def custody(tmp_path):
    source, other = tmp_path / "shared.sqlite", tmp_path / "other.sqlite"
    identities = []
    for path, count, total, prefix in (
        (source, 156, 199682910, "shared"),
        (other, 72, 95010110, "accepted"),
    ):
        identity = AllowanceLedger.initialize(path, Decimal("0.30"))
        identities.append(identity)
        with sqlite3.connect(path) as db:
            db.execute("UPDATE policy SET enabled=0")
            for i in range(count):
                charge = total // count + (i < total % count)
                db.execute(
                    "INSERT INTO attempts VALUES(?,?,?,1)",
                    (f"{prefix}-{i}", charge + 100, charge),
                )
        path.chmod(0o600)
    holds = []
    for i in range(19):
        amount = 255886201 // 19 + (i < 255886201 % 19)
        holds.append({"id": f"legacy-{i}", "reservation": amount, "evidence_sha256": "a" * 64})
    manifest = tmp_path / "manifest.json"
    data = {
        "version": 1,
        "source_sha256": digest(source),
        "imports": [{"path": str(other), "sha256": digest(other)}],
        "holds": holds,
        "provider_status": {
            "limit_usd": "2.00",
            "remaining_usd": "1.60",
            "usage_usd": "0.40",
            "limit_reset": None,
        },
        "readiness_usd": "0.10",
    }
    manifest.write_text(json.dumps(data), encoding="utf-8")
    manifest.chmod(0o600)
    return source, manifest, tmp_path / "canonical.sqlite", data, identities


def prepare(custody):
    from deploy.custody_handoff import prepare_handoff

    source, manifest, destination, _, _ = custody
    return prepare_handoff(source, manifest, destination)


def update(custody):
    custody[1].write_text(json.dumps(custody[3]), encoding="utf-8")


def test_preserves_identity_rows_charges_holds_and_finite_reserve(custody):
    source, _, destination, _, identities = custody
    original, before = rows(source), digest(source)
    receipt = prepare(custody)
    assert digest(source) == before
    with sqlite3.connect(destination) as db:
        policy = db.execute("SELECT * FROM policy").fetchone()
        assert policy == (1, identities[0], 755886201, 0)
        assert db.execute("SELECT COUNT(*) FROM attempts WHERE settled=1").fetchone() == (228,)
        assert db.execute("SELECT SUM(charged) FROM attempts WHERE settled=1").fetchone() == (
            294693020,
        )
        assert db.execute("SELECT COUNT(*) FROM attempts WHERE settled=0").fetchone() == (20,)
        assert db.execute("SELECT SUM(charged) FROM attempts").fetchone() == (655886201,)
    assert set(original).issubset(set(rows(destination)))
    assert receipt["remaining_usd"] == "0.100000000"
    assert receipt["enabled"] is False
    assert identities[0] not in json.dumps(receipt)
    assert prepare(custody)["already_prepared"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("limit_usd", "2.01"),
        ("limit_usd", "1.99"),
        ("remaining_usd", "0.35"),
        ("remaining_usd", "NaN"),
        ("usage_usd", "1.80"),
        ("usage_usd", "-0.1"),
        ("limit_reset", "monthly"),
    ],
)
def test_refuses_changed_cap_insufficient_remaining_or_invalid_status(custody, field, value):
    custody[3]["provider_status"][field] = value
    update(custody)
    with pytest.raises(ValueError, match="^Custody handoff refused$"):
        prepare(custody)
    assert not custody[2].exists()


@pytest.mark.parametrize("change", ["enabled", "tamper", "conflict", "hold", "extra", "reserve"])
def test_refuses_unsafe_or_changed_history(custody, change):
    source, _, _, data, _ = custody
    other = type(source)(data["imports"][0]["path"])
    if change == "enabled":
        with sqlite3.connect(source) as db:
            db.execute("UPDATE policy SET enabled=1")
        data["source_sha256"] = digest(source)
    elif change == "tamper":
        data["source_sha256"] = "0" * 64
    elif change == "conflict":
        with sqlite3.connect(other) as db:
            db.execute("UPDATE attempts SET id='shared-0' WHERE id='accepted-0'")
        data["imports"][0]["sha256"] = digest(other)
    elif change == "hold":
        data["holds"][0]["id"] = "shared-0"
    elif change == "extra":
        with sqlite3.connect(source) as db:
            db.execute(
                "CREATE TRIGGER unsafe AFTER INSERT ON attempts BEGIN DELETE FROM policy; END"
            )
        data["source_sha256"] = digest(source)
    else:
        data["readiness_usd"] = "0.11"
    update(custody)
    with pytest.raises(ValueError, match="^Custody handoff refused$"):
        prepare(custody)
    assert not custody[2].exists()


def test_refuses_existing_wrong_destination_and_does_not_replace_it(custody):
    custody[2].write_bytes(b"retained conflicting custody")
    with pytest.raises(ValueError, match="^Custody handoff refused$"):
        prepare(custody)
    assert custody[2].read_bytes() == b"retained conflicting custody"


def test_interrupted_copy_leaves_no_spendable_or_partial_destination(custody, monkeypatch):
    import deploy.custody_handoff as handoff

    def interrupted(*args, **kwargs):
        raise OSError("synthetic disk refusal")

    monkeypatch.setattr(handoff.os, "replace", interrupted)
    with pytest.raises(ValueError, match="^Custody handoff refused$"):
        prepare(custody)
    assert not custody[2].exists()
    with sqlite3.connect(custody[0]) as db:
        assert db.execute("SELECT enabled FROM policy").fetchone() == (0,)


def test_provider_gap_zero_does_not_release_any_legacy_hold(custody):
    custody[3]["provider_status"]["usage_usd"] = "0.20"
    update(custody)
    prepare(custody)
    with sqlite3.connect(custody[2]) as db:
        assert db.execute("SELECT COUNT(*) FROM attempts WHERE settled=0").fetchone() == (19,)
        assert db.execute("SELECT allowance FROM policy").fetchone() == (650579221,)
