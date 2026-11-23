"""Private qualification evidence, never a real key or current-host acceptance."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from deploy.artifact import files
from deploy.host_config import load_host_settings
from eval.tests.test_host_openrouter import PROVIDER_KEY, fixture_reader
from eval.tests.test_host_openrouter import openrouter_config as _openrouter_config

REFUSAL = "Provider qualification refused"


@pytest.fixture(name="openrouter_config")
def host_fixture(tmp_path):
    return _openrouter_config.__wrapped__(tmp_path)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def test_effective_profile_is_explicit_and_uses_the_selected_route(openrouter_config, monkeypatch):
    from deploy.provider_binding import configuration_fingerprint

    settings = load_host_settings(openrouter_config[0], read_private=fixture_reader)
    baseline = configuration_fingerprint(settings)
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "999")
    monkeypatch.setenv("LLM_PROVIDER", "scripted")
    assert configuration_fingerprint(settings) == baseline
    assert len(baseline) == 64 and PROVIDER_KEY not in baseline
    assert configuration_fingerprint(replace(settings, service_secret="z" * 32)) == baseline
    inference = {**settings.inference, "INFERENCE_INPUT_USD_PER_MILLION": "0.4"}
    assert configuration_fingerprint(replace(settings, inference=inference)) != baseline


def test_operating_profile_and_host_config_are_explicitly_bound(openrouter_config):
    from agent.lifecycle.operating import OperatingPolicy
    from deploy.provider_binding import configuration_fingerprint

    path, data, ledger = openrouter_config
    baseline = configuration_fingerprint(load_host_settings(path, read_private=fixture_reader))
    policy = OperatingPolicy(str(uuid4()), "a" * 64, "i-0123456789abcdef0", 100, 200)
    data.update(version=3, operating=policy.values(), operating_attempt_ceiling=101)
    data["admission_limits"]["maximum_sessions"] = 8
    path.write_text(json.dumps(data))
    before = ledger.status()
    settings = load_host_settings(path, read_private=fixture_reader)
    assert settings.operating == policy
    assert configuration_fingerprint(settings) != baseline
    assert ledger.status() == before
    data["version"] = 2
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_host_settings(path, read_private=fixture_reader)


def test_operating_host_cannot_exceed_accepted_eight_session_capacity(openrouter_config):
    from agent.lifecycle.operating import OperatingPolicy

    path, data, _ = openrouter_config
    policy = OperatingPolicy(str(uuid4()), "a" * 64, "i-0123456789abcdef0", 100, 200)
    data.update(version=3, operating=policy.values(), operating_attempt_ceiling=101)
    data["admission_limits"]["maximum_sessions"] = 9
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Host configuration refused"):
        load_host_settings(path, read_private=fixture_reader)


def test_operating_host_requires_a_pinned_absolute_model_attempt_ceiling(openrouter_config):
    from agent.lifecycle.operating import OperatingPolicy

    path, data, _ = openrouter_config
    policy = OperatingPolicy(str(uuid4()), "a" * 64, "i-0123456789abcdef0", 100, 200)
    data.update(version=3, operating=policy.values())
    data["admission_limits"]["maximum_sessions"] = 8
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Host configuration refused"):
        load_host_settings(path, read_private=fixture_reader)


@pytest.fixture
def binding_world(openrouter_config, monkeypatch):
    from deploy import provider_binding as module

    host_path, data, ledger = openrouter_config
    release = Path(data["release"])
    source = release / "agent/llm/openrouter.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"# synthetic model contract\n")
    sources = {"agent/llm/openrouter.py": digest(source.read_bytes())}
    manifest_path = release / "release.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["files"] = files(release)
    manifest_path.write_text(json.dumps(manifest))
    data["fingerprint"] = digest(manifest_path.read_bytes())
    host_path.write_text(json.dumps(data))
    settings = load_host_settings(host_path, read_private=fixture_reader)
    evidence = host_path.parent / "qualification"
    evidence.mkdir()
    report = json.dumps(
        dict(
            model=settings.model,
            accepted_for_local_replacement=True,
            automated_passed=True,
            milestone_summary=dict(gate_passed=True),
        )
    ).encode()
    reconciliation = json.dumps(
        dict(
            status="verified_offline_attribution_not_current_host_qualification",
            runtime_qualification_granted=False,
            accepted_report=dict(sha256=digest(report)),
            current_model_contract_sources={
                name: dict(git_sha256=value) for name, value in sources.items()
            },
        )
    ).encode()
    monkeypatch.setattr(module, "ACCEPTED_REPORT_SHA256", digest(report))
    monkeypatch.setattr(module, "RECONCILIATION_SHA256", digest(reconciliation))
    (evidence / "accepted-report.json").write_bytes(report)
    (evidence / "reconciliation.json").write_bytes(reconciliation)
    raw = module.candidate_binding(settings, issued_at=100, expires_at=200)
    path = evidence / "binding.json"
    path.write_bytes(raw)
    now = [150]

    def load(*, reader=fixture_reader, expected=None):
        return module.load_provider_binding(
            settings,
            path,
            expected or digest(path.read_bytes()),
            read_private=reader,
            clock=lambda: now[0],
        )

    return module, settings, path, ledger, now, load


def assert_refused(function):
    with pytest.raises(ValueError, match=f"^{REFUSAL}$") as caught:
        function()
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert PROVIDER_KEY not in str(caught.value)


def test_binding_observation_preserves_actual_allowance_and_private_metadata(binding_world):
    module, settings, path, ledger, now, load = binding_world
    before = ledger.status()
    binding = load()
    proof = binding.snapshot()
    assert binding.settings is settings and proof == binding.snapshot()
    for value in (binding, proof):
        assert str(path) not in repr(value)
        assert PROVIDER_KEY not in repr(value)
        assert digest(PROVIDER_KEY.encode()) not in repr(value)
    assert ledger.status() == before and before["uncertain"] == 1
    assert json.loads(path.read_bytes())["configuration_fingerprint"] == (
        module.configuration_fingerprint(settings)
    )


@pytest.mark.parametrize(
    "target", ["binding", "report", "reconciliation", "config", "service", "readiness"]
)
@pytest.mark.parametrize("mutation", ["change", "replace"])
def test_startup_refuses_earlier_file_changes_during_later_private_read(
    binding_world, target, mutation
):
    _, settings, path, _, _, load = binding_world
    earlier = {
        "binding": path,
        "report": path.parent / "accepted-report.json",
        "reconciliation": path.parent / "reconciliation.json",
        "config": settings.private_files[0],
        "service": settings.private_files[1],
        "readiness": settings.private_files[2],
    }[target]
    changed = []

    def reader(current, limit):
        raw = fixture_reader(current, limit)
        if current == settings.private_files[3]:
            before = earlier.read_bytes()
            if mutation == "change":
                earlier.write_bytes(before + b" ")
            else:
                replacement = earlier.with_name(earlier.name + ".replacement")
                replacement.write_bytes(before)
                replacement.replace(earlier)
            changed.append(earlier)
        return raw

    assert_refused(lambda: load(reader=reader))
    assert changed == [earlier]


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("version", 2),
        ("provider", "bedrock"),
        ("model", "google/gemini-2.5-flash"),
        ("release_fingerprint", "0" * 64),
        ("configuration_fingerprint", "0" * 64),
        ("accepted_report_sha256", "0" * 64),
        ("reconciliation_sha256", "0" * 64),
        ("provider_key_sha256", "0" * 64),
        ("ledger_identity", "00000000-0000-4000-8000-000000000000"),
        ("issued_at", True),
        ("issued_at", 151),
        ("expires_at", 150),
        ("expires_at", 100 + 60 * 86400 + 1),
        ("expires_at", 151.0),
    ],
)
def test_bound_route_fingerprints_and_interval_refuse(binding_world, field, value):
    _, _, path, _, _, load = binding_world
    data = json.loads(path.read_bytes())
    data[field] = value
    path.write_text(json.dumps(data))
    assert_refused(load)


@pytest.mark.parametrize("mutation", ["extra", "missing", "duplicate", "oversized", "digest"])
def test_binding_shape_and_operator_pin_cannot_be_bypassed(binding_world, mutation):
    _, _, path, _, _, load = binding_world
    data = json.loads(path.read_bytes())
    if mutation == "extra":
        data["ready"] = True
    elif mutation == "missing":
        del data["provider_key_sha256"]
    elif mutation == "duplicate":
        before = path.read_bytes()
        duplicate = before.replace(b'"version":1', b'"version":1,"version":1')
        assert duplicate != before
        path.write_bytes(duplicate)
        return assert_refused(load)
    elif mutation == "oversized":
        path.write_bytes(b" " * 16385)
        return assert_refused(load)
    elif mutation == "digest":
        return assert_refused(lambda: load(expected="0" * 64))
    path.write_text(json.dumps(data))
    assert_refused(load)


@pytest.mark.parametrize("name", ["binding.json", "accepted-report.json", "reconciliation.json"])
def test_private_evidence_changes_require_restart_and_are_revalidated(binding_world, name):
    _, _, path, _, _, load = binding_world
    pin = digest(path.read_bytes())
    binding = load()
    captured = binding.snapshot()
    target = path.parent / name
    target.write_bytes(target.read_bytes() + b" ")
    assert binding.snapshot() == captured
    assert_refused(lambda: load(expected=pin))
    target.unlink()
    assert binding.snapshot() == captured
    assert_refused(lambda: load(expected=pin))


def test_expiry_is_runtime_but_file_replacement_takes_effect_on_restart(binding_world):
    _, _, path, _, now, load = binding_world
    binding = load()
    captured = binding.snapshot()
    now[0] = 200
    assert_refused(binding.snapshot)
    now[0] = 150
    copy = path.with_suffix(".new")
    copy.write_bytes(path.read_bytes())
    copy.replace(path)
    assert binding.snapshot() == captured
    assert load().snapshot() != captured


@pytest.mark.parametrize("target", ["source", "key", "configuration"])
def test_changed_contract_or_custody_is_revalidated_at_startup(binding_world, target):
    _, settings, _, _, _, load = binding_world
    binding = load()
    path = (
        settings.release / "agent/llm/openrouter.py"
        if target == "source"
        else settings.private_files[-1]
        if target == "key"
        else settings.private_files[0]
    )
    if target == "configuration":
        data = json.loads(path.read_bytes())
        data["inference"]["INFERENCE_WAIT_SECONDS"] = "2"
        path.write_text(json.dumps(data))
    else:
        path.write_bytes(path.read_bytes() + b" ")
    assert binding.snapshot()
    assert_refused(load)


def test_runtime_observations_never_read_or_hash_protected_files(binding_world, monkeypatch):
    _, _, _, _, _, load = binding_world
    entered = []
    allowed = [True]

    def reader(path, limit):
        assert allowed[0], "Runtime private read"
        entered.append(path)
        return path.read_bytes()

    binding = load(reader=reader)
    before = len(entered)
    allowed[0] = False
    monkeypatch.setattr(Path, "read_bytes", lambda _: pytest.fail("Runtime disk read"))
    assert binding.snapshot() == binding.snapshot()
    assert len(entered) == before


def test_reviewed_source_bugfix_with_new_verified_release_binding_is_accepted(binding_world):
    module, old_settings, path, _, now, _ = binding_world
    source = old_settings.release / "agent/llm/openrouter.py"
    source.write_bytes(b"# reviewed bugfix; offline audit owns source decisions\n")
    manifest_path = old_settings.release / "release.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["files"] = files(old_settings.release)
    manifest_path.write_text(json.dumps(manifest))
    host_path = old_settings.private_files[0]
    data = json.loads(host_path.read_bytes())
    data["fingerprint"] = digest(manifest_path.read_bytes())
    host_path.write_text(json.dumps(data))
    settings = load_host_settings(host_path, read_private=fixture_reader)
    path.write_bytes(module.candidate_binding(settings, issued_at=100, expires_at=200))
    assert module.load_provider_binding(
        settings, path, digest(path.read_bytes()), read_private=fixture_reader, clock=lambda: now[0]
    ).snapshot()


def test_private_reader_refusal_is_redacted_and_no_nonposix_fallback_exists(binding_world):
    module, settings, path, _, _, load = binding_world

    def denied(*_):
        raise RuntimeError(PROVIDER_KEY + str(path))

    assert_refused(lambda: load(reader=denied))
    if __import__("os").name != "posix":
        assert_refused(
            lambda: module.load_provider_binding(settings, path, digest(path.read_bytes()))
        )


def test_production_evidence_pins_match_but_source_hashes_are_only_an_offline_record():
    from deploy.provider_binding import (
        ACCEPTED_REPORT_SHA256,
        RECONCILIATION_SHA256,
    )

    root = Path(__file__).resolve().parents[2]
    raw = (root / "eval/evidence/cap06-openrouter-reconciliation-20261024.json").read_bytes()
    evidence = json.loads(raw)
    assert digest(raw) == RECONCILIATION_SHA256
    assert evidence["accepted_report"]["sha256"] == ACCEPTED_REPORT_SHA256
    assert len(evidence["current_model_contract_sources"]) == 20
