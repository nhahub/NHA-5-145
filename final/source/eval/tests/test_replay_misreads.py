import asyncio
import json
from types import SimpleNamespace

import pytest

from agent.llm.contract import LLMChunk
from eval import replay_misreads as rm

MUTATE = {"all": [{"path": "intent", "equals": "mutate"}]}


def capture(message="اعمل الطلب", output=None, version="intent-v36"):
    return {
        "prompt_version": version,
        "schema_version": 10,
        "system": 'Shopping Copilot intent context: {"a":1}\nInstructions old.',
        "messages": [{"role": "shopper", "content": message}],
        "response_schema": {"type": "object"},
        "max_tokens": 1536,
        "temperature": 0,
        "output": json.dumps(output or {"intent": "navigate"}),
    }


def case(expect, case_id="c1"):
    return rm.Case(case_id, "label", "intent", "اعمل الطلب", expect, capture())


def fake_current(c):
    return rm._request_from(c.captured, system="NEW")


class FakeClient:
    def __init__(self, replies, cost=0.001):
        self.replies = replies
        self.calls = []
        self.call_metadata = []
        self.cost = cost

    async def complete(self, request):
        self.calls.append(request)
        self.call_metadata.append(SimpleNamespace(usage={"cost": self.cost}))
        yield LLMChunk(text=self.replies(request))


def write_cases(tmp_path):
    source = tmp_path / "captures.jsonl"
    source.write_text(
        "\n".join(json.dumps(capture(message=f"m{n}")) for n in range(1, 200)), encoding="utf-8"
    )
    return rm.build_case_files(source, tmp_path / "cases")


def test_build_and_load_cases_roundtrip(tmp_path):
    written = write_cases(tmp_path)
    assert len(written) == len(rm.CASE_TABLE)
    cases = {c.case_id: c for c in rm.load_cases(tmp_path / "cases")}
    assert cases["b7-180"].message == "m180"
    assert cases["b7-180"].expect == rm._SUBMIT
    assert cases["b5-103"].expect == rm._OPEN


def test_load_cases_requires_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        rm.load_cases(tmp_path)


def test_expectations_are_data():
    expect = {"all": [{"path": "intent", "equals": "mutate"}, {"path": "c.t", "in": ["x"]}]}
    assert rm.evaluate(expect, {"intent": "mutate", "c": {"t": "x"}}, "m")
    assert not rm.evaluate(expect, {"intent": "mutate"}, "m")
    assert not rm.evaluate(expect, None, "m")
    assert rm.evaluate(rm._QUOTE, {"intent": "cart_edit", "cart_source": "now"}, "now")
    assert not rm.evaluate(rm._QUOTE, {"intent": "cart_edit", "cart_source": "old"}, "now")
    assert rm.evaluate(rm._QUOTE, {"intent": "find_products"}, "now")
    assert rm.evaluate(rm._OPEN, {"intent": "find_products", "request_mode": "open"}, "m")
    assert rm.parse_output('noise {"a": 1} tail') == {"a": 1}
    assert rm.parse_output("not json") is None


def test_dry_run_makes_zero_calls_and_prints_plan(tmp_path, capsys):
    write_cases(tmp_path)

    def boom():
        raise AssertionError("client must not be created in a dry run")

    cases_dir = str(tmp_path / "cases")
    code = rm.main(
        ["run", "--cases", cases_dir, "--repeats", "3", "--dry-run"], client_factory=boom
    )
    out = capsys.readouterr().out
    assert code == 0
    assert f"{len(rm.CASE_TABLE) * 2 * 3} calls" in out
    assert "estimated cost $" in out
    assert "zero model calls" in out


def test_real_run_requires_max_spend(tmp_path):
    write_cases(tmp_path)
    with pytest.raises(SystemExit):
        rm.main(["run", "--cases", str(tmp_path / "cases")], client_factory=lambda: None)


def test_run_scores_captured_vs_current_and_reports_cost():
    c = case(MUTATE)
    client = FakeClient(
        lambda r: '{"intent": "mutate"}' if r.system == "NEW" else '{"intent": "navigate"}'
    )
    report = asyncio.run(rm.run_replay([c], client, repeats=3, max_spend=1.0, builder=fake_current))
    assert report["results"]["c1"] == {"captured": [0, 3], "current": [3, 3]}
    assert report["calls"] == 6
    assert report["spent_usd"] == pytest.approx(0.006)
    assert not report["stopped_on_cap"]
    table = rm.format_table([c], report)
    assert "0/3" in table
    assert "3/3" in table


def test_spend_cap_stops_the_run_before_exceeding_it():
    client = FakeClient(lambda r: '{"intent": "mutate"}', cost=0.004)
    report = asyncio.run(
        rm.run_replay([case(MUTATE)], client, repeats=10, max_spend=0.01, builder=fake_current)
    )
    assert report["stopped_on_cap"]
    assert len(client.calls) == report["calls"] < 20
    assert report["spent_usd"] <= 0.01 + 0.004


def test_cap_below_one_estimate_makes_no_call():
    client = FakeClient(lambda r: "{}")
    report = asyncio.run(
        rm.run_replay([case(MUTATE)], client, repeats=1, max_spend=1e-9, builder=fake_current)
    )
    assert client.calls == []
    assert report["stopped_on_cap"]
