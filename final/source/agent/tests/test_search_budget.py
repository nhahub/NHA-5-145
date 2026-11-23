"""A first search is not lost to one wasted catalogue decision (reliability ticket 01).

Observed through the Agent HTTP API with a scripted model. Captures #118-#120: the first
decision was `details` with no ids, the second `execute`, the interpreter handed the request
back to search, and the turn ended in the exhausted fallback with products one step away.
"""

import json

import pytest
from pydantic import ValidationError

from agent.app import create_app
from agent.catalogue_contract import DetailsQuery
from agent.event_log import MAX_REJECTIONS, REJECTION_CODES, MemorySink
from agent.llm import LLMSettings
from agent.tests.http_client import TestClient
from agent.tests.test_advice import RecordingModel, decision
from agent.tests.test_catalogue_retrieval import Reads, _recommend, _search
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot

EMPTY_DETAILS = {"kind": "details", "query": {"ids": []}}
EXECUTE = {"kind": "execute"}
FIND_PRODUCTS = decision(intent="find_products")
EXHAUSTED_TEXT = "ما قدرتش أكمّل البحث"


def ask(*answers, text="عايز جزمة جري", reads=None):
    sink = MemorySink()
    model, reads = RecordingModel(*answers), reads or Reads()
    app = create_app(
        llm_settings=LLMSettings(provider="groq", model="test"),
        llm_client=model,
        catalogue_client=reads,
        catalogue_retrieval_enabled=True,
        event_sink=sink,
    )
    with TestClient(app) as client:
        sid = client.post("/sessions").json()["session_id"]
        client.post(f"/sessions/{sid}/messages", json={"text": text, "snapshot": home_snapshot()})
        events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
    turns = [r for r in sink.records if r["event"] == "retrieval_turn"]
    return events, model, turns


def cards(events):
    return [c for e in events if e["event"] == "suggestions" for c in e["data"]["suggestions"]]


def shown(events):
    return json.dumps(events, ensure_ascii=False)


def test_execute_hand_back_search_recommend_finishes_with_a_decision_to_spare():
    events, model, (turn,) = ask(
        EMPTY_DETAILS, EXECUTE, FIND_PRODUCTS, _search("running shoes"), _recommend("p-1")
    )
    assert len(model.requests) == 5
    assert EXHAUSTED_TEXT not in shown(events)
    assert "suggestions" in [e["event"] for e in events]
    assert turn["outcome"] == "recommend"
    assert turn["decisions"] <= 3


def test_one_rejected_decision_on_the_way_does_not_end_the_turn():
    events, _, (turn,) = ask(
        EXECUTE, FIND_PRODUCTS, {"kind": "teleport"}, _search(), _recommend("p-1")
    )
    assert EXHAUSTED_TEXT not in shown(events)
    assert turn["outcome"] == "recommend"
    assert turn["rejections"] == ["decision_schema"]


def test_a_budget_that_runs_out_after_reads_shows_the_best_found_products_in_arabic():
    # Live check: the model spent every decision on reads and never recommended.
    events, model, (turn,) = ask(_search("a"), _search("b"), _search("c"))
    assert len(model.requests) == 3  # no extra model call to build the answer
    text = shown(events)
    assert EXHAUSTED_TEXT not in text
    assert "دي المنتجات اللي لقيتها لطلبك:" in text
    assert "suggestions" in [e["event"] for e in events]
    assert [c["id"] for c in cards(events)] == ["p-0", "p-1", "p-2"]
    assert events[-1]["event"] == "done"
    assert turn["outcome"] == "best_found"


def test_the_best_found_line_is_english_for_an_english_request():
    events, model, (turn,) = ask(
        _search("a"), _search("b"), _search("c"), text="I want running shoes"
    )
    assert "Here's what I found for your request:" in shown(events)
    assert len(cards(events)) == 3
    assert turn["outcome"] == "best_found"


def test_the_latest_read_that_returned_products_is_what_is_shown():
    class LastSearchEmpty(Reads):
        async def search(self, query):
            result = await super().search(query)
            if query.query == "empty":
                return result.model_copy(update={"candidates": []})
            return result

    events, _, (turn,) = ask(
        _search("full"), _search("empty"), _search("c"), reads=LastSearchEmpty()
    )
    assert turn["outcome"] == "best_found"
    assert "دي المنتجات اللي لقيتها لطلبك:" in shown(events)


def test_a_budget_that_runs_out_with_no_products_found_keeps_the_fallback_question():
    class Nothing(Reads):
        async def search(self, query):
            result = await super().search(query)
            return result.model_copy(update={"candidates": []})

    events, model, (turn,) = ask(_search("a"), _search("b"), _search("c"), reads=Nothing())
    assert EXHAUSTED_TEXT in shown(events)
    assert cards(events) == []
    assert turn["outcome"] == "exhausted"
    events, _, (turn,) = ask({}, {}, {})
    assert EXHAUSTED_TEXT in shown(events) and turn["outcome"] == "exhausted"


def test_the_turn_record_stays_in_its_allow_list_and_carries_no_shopper_text():
    text = "عايز جزمة جري سرية-123"
    for answers in (({}, {}, {}), (_search("a"), _search("b"), _search("c"))):
        _, _, (turn,) = ask(*answers, text=text)
        assert text not in json.dumps(turn, ensure_ascii=False)
        assert len(turn["rejections"]) <= MAX_REJECTIONS
        assert set(turn["rejections"]) <= REJECTION_CODES
        assert turn["outcome"] in {"exhausted", "best_found"}
        assert turn["decisions"] == 3


def test_details_with_no_ids_is_refused_by_the_schema_and_never_reaches_code():
    with pytest.raises(ValidationError):
        DetailsQuery(ids=[])
    events, model, (turn,) = ask(EMPTY_DETAILS, _search(), _recommend("p-1"))
    assert turn["rejections"] == ["decision_schema"]
    assert EXHAUSTED_TEXT not in shown(events)
    assert len(model.requests) == 3


class ClothingOnly(Reads):
    """Finds products only for a search that filters by the catalogue's own `clothing` key."""

    async def search(self, query):
        self.calls.append(query)
        found = any(
            getattr(p, "value", None) in ("clothing", "daily_workouts") for p in query.predicates
        )
        base = await Reads().search(query)
        return base if found else base.model_copy(update={"candidates": []})


def _filtered(field, value, text="trousers"):
    return {
        "kind": "search",
        "query": {"query": text, "predicates": [{"field": field, "op": "eq", "value": value}]},
    }


def feedback_sent(model, request_index):
    context = json.loads(model.requests[request_index].messages[0].content)
    return json.dumps(context["validation_feedback"], ensure_ascii=False)


def test_a_display_label_is_read_as_the_catalogue_key_before_the_read():
    reads = ClothingOnly()
    events, model, (turn,) = ask(_filtered("category", "Clothing"), _recommend("p-1"), reads=reads)
    assert [p.value for p in reads.calls[0].predicates] == ["clothing"]
    assert turn["outcome"] == "recommend" and turn["rejections"] == []
    assert len(model.requests) == 2


def test_an_arabic_label_or_alias_is_read_as_its_key():
    for field, word, key in (
        ("category", "الملابس", "clothing"),
        ("use", "workouts", "daily_workouts"),
    ):
        reads = ClothingOnly()
        ask(_filtered(field, word), _recommend("p-1"), reads=reads)
        assert reads.calls[0].predicates[0].value == key


def test_a_value_that_is_no_catalogue_key_is_refused_with_the_allowed_keys_then_repaired():
    reads = ClothingOnly()
    events, model, (turn,) = ask(
        _filtered("use", "gym"),
        _filtered("use", "daily_workouts"),
        _recommend("p-1"),
        reads=reads,
    )
    assert turn["rejections"] == ["unknown_filter_value"]
    fed_back = feedback_sent(model, 1)
    for key in ("daily_workouts", "hiking", "formal_events"):
        assert key in fed_back
    assert len(reads.calls) == 2  # the refused search never reached the catalogue
    assert reads.calls[0].predicates[0].value == "daily_workouts"
    assert turn["outcome"] == "recommend"
    assert EXHAUSTED_TEXT not in shown(events)


def test_an_identical_search_that_found_nothing_is_refused_before_the_read():
    reads = ClothingOnly()
    nothing = _filtered("category", "shoes")
    events, model, (turn,) = ask(nothing, nothing, _filtered("category", "clothing"), reads=reads)
    assert turn["rejections"] == ["repeated_empty_search"]
    assert "returned no products" in feedback_sent(model, 2)
    assert "loosen or change the filters" in feedback_sent(model, 2)
    assert len(reads.calls) == 2  # the repeat was not read again
    assert turn["outcome"] == "best_found"


def test_a_changed_search_after_an_empty_one_is_not_refused():
    reads = ClothingOnly()
    _, _, (turn,) = ask(
        _filtered("category", "shoes"),
        _filtered("category", "clothing"),
        _recommend("p-1"),
        reads=reads,
    )
    assert turn["rejections"] == [] and turn["outcome"] == "recommend"
