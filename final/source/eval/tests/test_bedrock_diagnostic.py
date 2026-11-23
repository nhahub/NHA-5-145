import asyncio
import json
from contextlib import contextmanager
from decimal import Decimal

import pytest

from agent.inference.ledger import AllowanceLedger
from agent.llm.contract import LLMChunk
from eval import bedrock_diagnostic as diagnostic


class FakeClient:
    call_metadata = ()

    def __init__(self, check=lambda: None, error=None):
        self.check, self.error, self.calls = check, error, 0

    async def complete(self, request):
        self.check()
        self.calls += 1
        assert request.provider_attempt_limit == 1
        assert request.max_tokens == 1536
        if self.error:
            raise self.error
        yield LLMChunk(text="{}")


def factory(client):
    @contextmanager
    def open_client():
        yield client

    return open_client


def test_default_only_prepares_and_never_builds_credentialed_client(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(diagnostic, "OUTPUT_ROOT", tmp_path)
    monkeypatch.setattr(diagnostic, "live_client", lambda: pytest.fail("credential access"))
    assert diagnostic.main([]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["maximum_calls"] == 1
    assert plan["maximum_cost_usd"] == "0.02"
    assert plan["reservation_usd"] == "0.015"
    assert plan["case_id"] == "ar-01"
    assert plan["model"] == "openai.gpt-oss-20b-1:0"
    assert not (tmp_path / "allowance.sqlite").exists()
    assert not (tmp_path / "claim.json").exists()


def test_explicit_run_requires_owner_approval_reference_before_any_state(tmp_path):
    with pytest.raises(ValueError, match="approval"):
        asyncio.run(diagnostic.run_once(tmp_path, "", client_factory=factory(FakeClient())))
    assert not (tmp_path / "claim.json").exists()


def test_fixed_plan_does_not_silently_change_after_review(tmp_path, monkeypatch):
    plan = diagnostic.prepare(tmp_path)
    monkeypatch.setattr(diagnostic, "build_plan", lambda: {**plan, "request_sha256": "changed"})
    with pytest.raises(ValueError, match="plan"):
        diagnostic.prepare(tmp_path)


@pytest.mark.parametrize("error", [None, RuntimeError("provider-secret"), asyncio.CancelledError()])
def test_only_one_entry_and_full_reservation_survives_every_outcome(tmp_path, error):
    def check():
        identity = json.loads((tmp_path / "claim.json").read_text())["ledger_identity"]
        status = AllowanceLedger(tmp_path / "allowance.sqlite", identity).status()
        assert Decimal(status["accounted_usd"]) == Decimal("0.015")
        assert status["attempts"] == 1

    client = FakeClient(check=check, error=error)
    if isinstance(error, asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(
                diagnostic.run_once(tmp_path, "owner-approved-001", client_factory=factory(client))
            )
    else:
        report = asyncio.run(
            diagnostic.run_once(tmp_path, "owner-approved-001", client_factory=factory(client))
        )
        assert report["cost_usd"] is None
        assert report["semantic_check"]["exact"] is False if error is None else report["failure"]
    assert client.calls == 1
    assert "provider-secret" not in (tmp_path / "result.json").read_text()
    with pytest.raises(FileExistsError):
        asyncio.run(
            diagnostic.run_once(tmp_path, "second-reference", client_factory=factory(client))
        )
    assert client.calls == 1


def test_sdk_construction_failure_is_recorded_without_replenishing_budget(tmp_path):
    @contextmanager
    def broken():
        raise RuntimeError("credential-secret")
        yield

    report = asyncio.run(diagnostic.run_once(tmp_path, "owner-approved-001", client_factory=broken))
    assert report["failure"] == "RuntimeError"
    assert report["ledger"]["uncertain"] == 1
    assert "credential-secret" not in json.dumps(report)


def test_request_change_during_credential_setup_cannot_reach_provider(tmp_path, monkeypatch):
    from dataclasses import replace

    case, request = diagnostic._request()
    client = FakeClient()

    @contextmanager
    def changed_during_login():
        monkeypatch.setattr(
            diagnostic, "_request", lambda: (case, replace(request, system="changed"))
        )
        yield client

    report = asyncio.run(
        diagnostic.run_once(tmp_path, "owner-approved-001", client_factory=changed_during_login)
    )
    assert client.calls == 0
    assert report["failure"] == "ValueError"
    assert report["ledger"]["uncertain"] == 1
