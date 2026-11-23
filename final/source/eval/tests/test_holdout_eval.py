"""No model downloads or paid requests: fake artifacts and HTTP transport only."""

import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from eval import holdout_eval as subject


def test_budget_decimal_edge_unknown_cost_and_no_replay(tmp_path):
    ledger = subject.BudgetLedger(tmp_path / "ledger.json", {"release": "abc"})
    ledger.reserve("first", Decimal("0.199"))
    ledger.finish("first", None, {"prediction": "__failure__"})
    ledger.reserve("second", Decimal("0.001"))
    assert ledger.exposure == Decimal("0.20")
    with pytest.raises(subject.BudgetExceeded):
        ledger.reserve("third", Decimal("0.0000001"))
    with pytest.raises(ValueError, match="attempted"):
        ledger.reserve("first", Decimal("0.0001"))
    resumed = subject.BudgetLedger(tmp_path / "ledger.json", {"release": "abc"})
    assert resumed.exposure == Decimal("0.20")
    assert resumed.attempts["second"]["status"] == "interrupted"
    assert resumed.attempts["second"]["result"]["prediction"] == "__failure__"


@pytest.mark.parametrize("cost", [float("nan"), float("inf"), -1, True, "NaN", None])
def test_bad_cost_retains_reservation(tmp_path, cost):
    ledger = subject.BudgetLedger(tmp_path / "ledger.json", {})
    ledger.reserve("one", Decimal("0.002"))
    ledger.finish("one", cost, {"prediction": "help"})
    assert ledger.exposure == Decimal("0.002")
    assert ledger.attempts["one"]["actual_cost_usd"] is None


def test_known_cost_settles_and_changed_binding_refused(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = subject.BudgetLedger(path, {"source": "old"})
    ledger.reserve("one", Decimal("0.002"))
    ledger.finish("one", 0.00012, {"prediction": "help"})
    assert ledger.exposure == Decimal("0.00012")
    with pytest.raises(ValueError, match="changed"):
        subject.BudgetLedger(path, {"source": "new"})


def test_exclusive_lock_fails_closed(tmp_path):
    path = tmp_path / "lock"
    with (
        subject.exclusive_lock(path),
        pytest.raises(ValueError, match="locked"),
        subject.exclusive_lock(path),
    ):
        pytest.fail("must not acquire existing lock")
    assert not path.exists()


def test_invalid_and_missing_predictions_keep_denominator_and_fixed_labels():
    labels = ["help", "advice"]
    records = [
        {"case_id": "a", "expected": {"intent": "help"}, "language_group": "english"},
        {"case_id": "b", "expected": {"intent": "advice"}, "language_group": "english"},
        {"case_id": "c", "expected": {"intent": "help"}, "language_group": "english"},
    ]
    result = subject.score(
        records,
        [{"case_id": "a", "prediction": "bogus"}, {"case_id": "b", "prediction": "advice"}],
        labels,
    )
    assert result["accuracy"] == pytest.approx(1 / 3)
    assert result["count"] == 3
    assert result["failure_count"] == 2
    assert result["missing_attempts"] == ["c"]
    assert result["confusion_matrix"] == [[0, 0, 2], [0, 1, 0]]
    assert result["macro_f1"] == 0.5


def test_artifact_and_report_hashes_checked_before_loading(tmp_path, monkeypatch):
    artifact = tmp_path / "model.joblib"
    report = tmp_path / "selection.json"
    artifact.write_bytes(b"trusted local model")
    report.write_text("{}", encoding="utf-8")
    protocol = {
        "families": [
            {
                "family": "lr",
                "artifact": artifact.name,
                "sha256": subject.digest(artifact),
                "selection_report": report.name,
                "selection_report_sha256": subject.digest(report),
            }
        ]
    }
    subject.verify_artifacts(protocol, tmp_path, tmp_path)
    for target in (artifact, report):
        original = target.read_bytes()
        target.write_bytes(b"tampered")
        with pytest.raises(ValueError, match="hash"):
            subject.verify_artifacts(protocol, tmp_path, tmp_path)
        target.write_bytes(original)


def llm_protocol():
    return {
        "labels": ["help", "advice"],
        "llm": {
            "system": "Classify only",
            "model": "google/gemini-2.5-flash",
            "temperature": 0,
            "max_tokens": 32,
            "response_schema": {
                "type": "object",
                "properties": {"intent": {"type": "string", "enum": ["help", "advice"]}},
                "required": ["intent"],
                "additionalProperties": False,
            },
        },
    }


def test_same_text_only_input_and_exact_output_validation():
    protocol = llm_protocol()
    message = "  عاوز help!  "
    request = subject.make_request(protocol, {"case_id": "id", "input": {"message": message}})
    assert len(request.messages) == 1
    assert request.messages[0].content == message
    assert request.max_tokens == 32
    for bad in ('{"intent":"bogus"}', '{"intent":"help","other":0}', "not JSON"):
        with pytest.raises(ValueError):
            request.response_validator(bad)


def test_llm_reservation_precedes_network_and_interruption_never_replays(tmp_path):
    ledger = subject.BudgetLedger(tmp_path / "ledger.json", {})
    records = [{"case_id": "one", "input": {"message": "test input"}}]

    class InterruptedClient:
        call_metadata = []

        async def complete(self, request):
            saved = json.loads((tmp_path / "ledger.json").read_text())
            assert saved["attempts"]["one"]["status"] == "inflight"
            raise KeyboardInterrupt
            yield  # pragma: no cover

    with pytest.raises(KeyboardInterrupt):
        asyncio.run(subject.evaluate_llm(records, llm_protocol(), InterruptedClient(), ledger))
    resumed = subject.BudgetLedger(tmp_path / "ledger.json", {})
    asyncio.run(subject.evaluate_llm(records, llm_protocol(), InterruptedClient(), resumed))
    assert resumed.attempts["one"]["status"] == "interrupted"


def test_fake_llm_invalid_output_is_failure_with_safe_cost_metadata(tmp_path):
    ledger = subject.BudgetLedger(tmp_path / "ledger.json", {})

    class FakeClient:
        call_metadata = []

        async def complete(self, request):
            self.call_metadata.append(
                SimpleNamespace(
                    generation_id="gen-123",
                    latency_ms=4,
                    usage={"cost": 0.0001},
                    failure_category=None,
                )
            )
            yield SimpleNamespace(text='{"intent":"invented"}')

    records = [{"case_id": "one", "input": {"message": "test"}}]
    asyncio.run(subject.evaluate_llm(records, llm_protocol(), FakeClient(), ledger))
    attempt = ledger.attempts["one"]
    assert attempt["result"]["prediction"] == "__failure__"
    assert attempt["actual_cost_usd"] == "0.0001"
    assert attempt["result"]["generation_id"] == "gen-123"


def test_actual_client_mock_http_matches_reservation_and_single_attempt(tmp_path):
    import httpx
    from pydantic import SecretStr

    from agent.llm.config import LLMSettings
    from agent.llm.openrouter import OpenRouterClient

    protocol = llm_protocol()
    records = [{"case_id": "one", "input": {"message": 'آ help " test'}}]
    ledger = subject.BudgetLedger(tmp_path / "ledger.json", {})
    requests = []

    def transport(request):
        requests.append(request)
        assert json.loads(ledger.path.read_text())["attempts"]["one"]["status"] == "inflight"
        if request.method == "GET":
            return httpx.Response(
                200, json={"data": {"limit": 2, "limit_remaining": 2, "limit_reset": None}}
            )
        payload = json.loads(request.content)
        expected = (
            Decimal(len(json.dumps(payload).encode()) + 4096) * Decimal("0.3")
            + Decimal(32) * Decimal("2.5")
        ) / 1_000_000
        assert expected == Decimal(ledger.attempts["one"]["reservation_usd"])
        assert payload["messages"][1]["content"] == records[0]["input"]["message"]
        return httpx.Response(
            200,
            json={
                "id": "gen-valid",
                "usage": {"cost": 0.0002},
                "choices": [{"finish_reason": "stop", "message": {"content": '{"intent":"help"}'}}],
            },
        )

    client = OpenRouterClient(
        LLMSettings(
            provider="openrouter",
            model=protocol["llm"]["model"],
            api_key=SecretStr("fake"),
            openrouter_total_limit=2,
        ),
        transport=httpx.MockTransport(transport),
    )
    asyncio.run(subject.evaluate_llm(records, protocol, client, ledger))
    asyncio.run(subject.evaluate_llm(records, protocol, client, ledger))
    assert [r.method for r in requests] == ["GET", "POST"]
    assert ledger.attempts["one"]["result"]["prediction"] == "help"
    assert ledger.exposure == Decimal("0.0002")


@pytest.mark.parametrize("command", ["offline", "llm"])
def test_entrypoint_hash_failure_precedes_loading_or_paid_client(tmp_path, monkeypatch, command):
    import joblib

    from agent.llm import openrouter
    from eval import holdout_release

    artifact = tmp_path / "artifact"
    artifact.write_bytes(b"tampered")
    data = {
        "protocol": {
            "families": [
                {
                    "family": "lr",
                    "artifact": "artifact",
                    "sha256": "wrong",
                    "selection_report": "report",
                    "selection_report_sha256": "wrong",
                }
            ]
        }
    }
    monkeypatch.setattr(holdout_release, "load_frozen_release", lambda *_: data)
    monkeypatch.setattr(joblib, "load", lambda *_: pytest.fail("unsafe artifact load"))
    monkeypatch.setattr(
        openrouter, "OpenRouterClient", lambda *_: pytest.fail("unsafe paid client")
    )
    with pytest.raises(ValueError, match="hash"):
        subject.run(
            command, tmp_path / "release", tmp_path / "output", tmp_path, tmp_path, root=tmp_path
        )
    assert not (tmp_path / "output").exists()


def test_local_text_is_unmodified_and_index_is_validated():
    received = []

    class FakeModel:
        def predict(self, texts):
            received.extend(texts)
            return [1]

    text = "  آ shopping! "
    assert subject.predict_local({"model": FakeModel()}, None, text, ["advice", "help"]) == "help"
    assert received == [text]


def test_budget_exhaustion_leaves_remaining_cases_unattempted(tmp_path):
    ledger = subject.BudgetLedger(tmp_path / "ledger.json", {})
    ledger.reserve("previous", Decimal("0.20"))
    ledger.finish("previous", None, {"prediction": "help"})
    client = SimpleNamespace(call_metadata=[], complete=lambda _: pytest.fail("over budget"))
    records = [{"case_id": "new", "input": {"message": "test"}}]
    asyncio.run(subject.evaluate_llm(records, llm_protocol(), client, ledger))
    assert "new" not in ledger.attempts


def test_score_reports_incomplete_separately_from_output_failures():
    records = [{"case_id": name, "expected": {"intent": "help"}} for name in "abc"]
    result = subject.score(
        records,
        [
            {"case_id": "a", "prediction": "help", "status": "complete"},
            {"case_id": "b", "prediction": "__failure__", "status": "startup_failure"},
        ],
        ["help", "advice"],
    )
    assert result["attempted_count"] == 1
    assert result["unattempted_count"] == 2
    assert result["status"] == "incomplete"
    assert result["accuracy"] == pytest.approx(1 / 3)


def test_offline_resume_does_not_replay_and_keeps_startup_and_per_case_timing(
    tmp_path, monkeypatch
):
    import joblib

    received = []

    class FakeModel:
        def predict(self, texts):
            received.extend(texts)
            return [0]

    monkeypatch.setattr(
        joblib,
        "load",
        lambda _: {"model": FakeModel(), "labels": ["help", "advice"], "encoder": None},
    )
    data = {
        "protocol": {
            "labels": ["help", "advice"],
            "families": [{"family": "lr", "artifact": "model.joblib"}],
        },
        "records": [
            {"case_id": "a", "input": {"message": " a "}},
            {"case_id": "b", "input": {"message": " b "}},
        ],
    }
    state = subject.evaluate_offline(data, tmp_path, tmp_path, tmp_path, {})
    subject.evaluate_offline(data, tmp_path, tmp_path, tmp_path, {})
    assert received == ["Show me a pair of shoes", " a ", " b "]
    result = state["families"]["lr"]
    assert len(result["startups"]) == 1
    assert result["startups"][0]["load_ms"] >= 0
    assert result["startups"][0]["warmup_ms"] >= 0
    assert all(row["latency_ms"] >= 0 for row in result["attempts"].values())


def test_report_keeps_all_contenders_and_unknown_cost_and_never_overwrites(tmp_path):
    protocol = {
        "labels": ["help", "advice"],
        "languages": ["english"],
        "families": [{"family": "lr"}],
    }
    data = {
        "protocol": protocol,
        "records": [{"case_id": "a", "expected": {"intent": "help"}, "language_group": "english"}],
    }
    subject.save_json(tmp_path / "run.json", {"binding": {}, "invocations": []})
    ledger = subject.BudgetLedger(tmp_path / "ledger.json", {})
    ledger.reserve("a", Decimal("0.002"))
    ledger.finish("a", None, {"prediction": "__failure__"})
    result = subject.report_results(data, tmp_path, {}, ledger.path)
    assert set(result["results"]) == {"lr", "llm"}
    assert result["results"]["lr"]["status"] == "incomplete"
    assert result["results"]["llm"]["status"] == "complete"
    assert result["results"]["llm"]["accuracy"] == 0
    assert result["cost"]["unknown_cost_count"] == 1
    assert result["cost"]["held_unknown_cost_usd"] == "0.002"
    original = (tmp_path / "report.json").read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        subject.report_results(data, tmp_path, {}, ledger.path)
    assert (tmp_path / "report.json").read_bytes() == original
