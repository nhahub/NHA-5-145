"""Ticket 05: a two-step message becomes a plan beside the active task.

Driven through the Agent's HTTP API with a scripted model. The plan holds only the Shopper's
words; each later step is interpreted by its own model call at its own turn.
"""

import json

import pytest
from pydantic import ValidationError

from agent.app import create_app
from agent.catalogue_retrieval import DECISION, MODEL_DECISION, RetrievalBudget, retrieve_products
from agent.event_log import MemorySink
from agent.llm import LLMSettings
from agent.planner import ScriptedPlanner
from agent.tests.http_client import TestClient
from agent.tests.test_advice import RecordingModel, advice
from agent.tests.test_catalogue_retrieval import Reads, active
from agent.tests.test_real_task import action_result, snapshot_at
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot

SHOPPER_TEXT = "ضيفلي الجزمة ديه للعربية بعدها افتح الدفع"
STEP_TWO = "افتح الدفع"
STEP_ONE_WORDS = "ضيفلي الجزمة ديه للعربية"
PLAN_EVENTS = {"plan_created", "plan_step_started", "plan_step_finished", "plan_finished"}


def intent(target="cart", **overrides) -> dict:
    return {
        "v": 10,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "intent": "navigate",
        "constraints": {"target": target},
        "missing_fields": [],
        "conflicting_fields": [],
        "needs_clarification": False,
        **overrides,
    }


def two_steps(target="cart", **overrides) -> dict:
    return intent(target, first_step=STEP_ONE_WORDS, remaining_steps=[STEP_TWO], **overrides)


def make_client(*replies, sink=None, **options):
    model = RecordingModel(*replies)
    app = create_app(
        llm_settings=LLMSettings(provider="groq", model="test", api_key=None),
        llm_client=model,
        **({"event_sink": sink} if sink is not None else {}),
        **options,
    )
    return TestClient(app), model


def start(client, text=SHOPPER_TEXT, snapshot=None):
    session_id = client.post("/sessions").json()["session_id"]
    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": text, "snapshot": snapshot or home_snapshot()},
    )
    assert response.status_code == 202
    return session_id


def stream(client, session_id):
    return parse_sse(client.get(f"/sessions/{session_id}/events?once=true").text)


def last_action(events):
    return [e["data"]["action"] for e in events if e["event"] == "action"][-1]


def complete(client, session_id, events, url):
    """Report the last action as done on a page at `url`; return the new snapshot."""
    snapshot = snapshot_at(url)
    response = client.post(
        f"/sessions/{session_id}/action-results", json=action_result(last_action(events), snapshot)
    )
    assert response.status_code == 202
    return snapshot


def names(events, wanted=None):
    return [e["event"] for e in events if wanted is None or e["event"] in wanted]


def run_two_steps(client, session_id):
    first = stream(client, session_id)
    complete(client, session_id, first, "/cart")
    second = stream(client, session_id)
    complete(client, session_id, second, "/checkout")
    return stream(client, session_id)


# --- Agent HTTP: the retrieval-off path (one interpretation call per step) ---------------


def test_two_steps_run_in_spoken_order_as_two_tasks_with_the_exact_stream_order():
    client, model = make_client(two_steps("cart"), intent("checkout"))
    session_id = start(client)
    events = run_two_steps(client, session_id)

    kinds = [e["event"] for e in events if e["event"] != "narration" and e["event"] != "action"]
    assert kinds == [
        "task_started",
        "plan_created",
        "plan_step_started",
        "done",
        "plan_step_finished",
        "task_started",
        "plan_step_started",
        "done",
        "plan_step_finished",
        "plan_finished",
    ]
    started = [e for e in events if e["event"] == "task_started"]
    assert len(started) == 2 and started[0]["data"]["task_id"] != started[1]["data"]["task_id"]
    urls = [e["data"]["action"].get("url") for e in events if e["event"] == "action"]
    assert urls == ["/cart", "/checkout"]


def test_stream_order_of_every_event_for_a_two_step_message():
    client, _ = make_client(two_steps("cart"), intent("checkout"))
    session_id = start(client)
    events = run_two_steps(client, session_id)
    flat = [
        (e["event"], e["data"].get("outcome", e["data"].get("position")))
        for e in events
        if e["event"] in PLAN_EVENTS | {"task_started", "done"}
    ]
    assert flat == [
        ("task_started", None),
        ("plan_created", None),
        ("plan_step_started", 1),
        ("done", None),
        ("plan_step_finished", "done"),
        ("task_started", None),
        ("plan_step_started", 2),
        ("done", None),
        ("plan_step_finished", "done"),
        ("plan_finished", "done"),
    ]
    # plan_created comes before any action of task 1.
    names_only = names(events)
    assert names_only.index("plan_created") < names_only.index("action")
    # plan_step_started(2) follows task_started(2) at once.
    second_start = [i for i, n in enumerate(names_only) if n == "task_started"][1]
    assert names_only[second_start + 1] == "plan_step_started"


def test_plan_events_carry_the_exact_payloads_and_one_based_positions():
    client, _ = make_client(two_steps("cart"), intent("checkout"))
    session_id = start(client)
    events = run_two_steps(client, session_id)
    by_name = {}
    for event in events:
        by_name.setdefault(event["event"], []).append(event["data"])
    created = by_name["plan_created"][0]
    plan_id = created["plan_id"]
    assert created["language"] == "ar"
    assert created["steps"] == [
        {"position": 1, "text": STEP_ONE_WORDS},
        {"position": 2, "text": STEP_TWO},
    ]
    task_ids = [d["task_id"] for d in by_name["task_started"]]
    assert [(d["plan_id"], d["position"], d["task_id"]) for d in by_name["plan_step_started"]] == [
        (plan_id, 1, task_ids[0]),
        (plan_id, 2, task_ids[1]),
    ]
    assert [(d["position"], d["outcome"]) for d in by_name["plan_step_finished"]] == [
        (1, "done"),
        (2, "done"),
    ]
    assert created["skipped"] == []
    assert by_name["plan_finished"] == [
        {
            "session_id": session_id,
            "plan_id": plan_id,
            "outcome": "done",
            "report": "خلصت طلبك:\n✓ ضيفلي الجزمة ديه للعربية\n✓ افتح الدفع",
        }
    ]


def test_step_two_is_interpreted_only_at_its_turn_against_the_latest_snapshot():
    client, model = make_client(two_steps("cart"), intent("checkout"))
    session_id = start(client)
    first = stream(client, session_id)
    assert len(model.requests) == 1  # nothing is interpreted ahead of time
    assert "plan_step_started" in names(first)

    complete(client, session_id, first, "/cart")
    assert len(model.requests) == 2
    second_request = model.requests[1]
    # The words of step 2 alone are interpreted, and the page seen is the latest one.
    assert second_request.messages[-1].content == STEP_TWO
    assert "http://localhost:4000/cart" in json.dumps(
        [m.content for m in second_request.messages] + [second_request.system],
        ensure_ascii=False,
    )
    # The first call was about the first step; no later step was pre-interpreted.
    assert model.requests[0].messages[-1].content == SHOPPER_TEXT


def test_a_missing_first_step_label_is_the_languages_generic_label_never_cut_from_the_message():
    client, _ = make_client(intent("cart", remaining_steps=[STEP_TWO]), intent("checkout"))
    session_id = start(client)
    created = next(e["data"] for e in stream(client, session_id) if e["event"] == "plan_created")
    assert created["steps"][0] == {"position": 1, "text": "الطلب الأول"}

    client, _ = make_client(
        intent("cart", language="en", dialect="english", remaining_steps=["open checkout"])
    )
    session_id = start(client, "open the cart then open checkout")
    created = next(e["data"] for e in stream(client, session_id) if e["event"] == "plan_created")
    assert created["language"] == "en"
    assert created["steps"][0] == {"position": 1, "text": "First request"}


def test_a_one_step_message_makes_one_model_call_and_no_plan_events():
    client, model = make_client(intent("cart"))
    session_id = start(client, "افتح السلة")
    events = stream(client, session_id)
    complete(client, session_id, events, "/cart")
    events = stream(client, session_id)
    assert len(model.requests) == 1
    assert not PLAN_EVENTS & set(names(events))
    assert names(events).count("task_started") == 1


def test_a_second_message_is_rejected_while_the_plan_runs_like_during_a_task():
    client, _ = make_client(two_steps("cart"), intent("checkout"))
    session_id = start(client)
    again = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "افتح الحساب", "snapshot": home_snapshot()},
    )
    assert again.status_code == 409
    # Between steps too: step 2's task is active as soon as step 1 ends.
    first = stream(client, session_id)
    complete(client, session_id, first, "/cart")
    between = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "افتح الحساب", "snapshot": home_snapshot()},
    )
    assert between.status_code == 409


def test_a_finished_plan_frees_the_session_for_a_new_message():
    client, _ = make_client(two_steps("cart"), intent("checkout"), intent("cart"))
    session_id = start(client)
    run_two_steps(client, session_id)
    again = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "افتح السلة", "snapshot": home_snapshot()},
    )
    assert again.status_code == 202


# --- Failure, pause and cancel -------------------------------------------------------------


def test_step_one_pausing_fails_it_skips_step_two_and_fails_the_plan_without_a_second_call():
    asking = two_steps("cart", needs_clarification=True, missing_fields=["target"])
    client, model = make_client(asking, "not json", "still not json")
    session_id = start(client)
    first = stream(client, session_id)
    question = last_action(first)
    assert question["type"] == "ask_shopper"
    # A step that asks a question keeps the plan waiting: nothing has finished yet.
    assert "plan_step_finished" not in names(first)

    client.post(
        f"/sessions/{session_id}/tasks/{question['task_id']}/answers",
        json={"question_id": question["action_id"], "text": "السلة", "snapshot": home_snapshot()},
    )
    events = stream(client, session_id)
    tail = [
        (e["event"], e["data"].get("position"), e["data"].get("outcome"))
        for e in events
        if e["event"] in {"plan_step_finished", "plan_finished"}
    ]
    assert tail == [
        ("plan_step_finished", 1, "failed"),
        ("plan_step_finished", 2, "skipped"),
        ("plan_finished", None, "failed"),
    ]
    assert names(events).count("task_started") == 1  # step 2 never started
    assert len(model.requests) == 3  # first call + the answer's call and its one repair


def test_cancelling_during_step_one_cancels_the_plan_and_skips_the_rest():
    client, model = make_client(two_steps("cart"), intent("cart"))
    session_id = start(client)
    stream(client, session_id)
    assert client.post(f"/sessions/{session_id}/stop").status_code == 202
    events = stream(client, session_id)
    tail = [
        (e["event"], e["data"].get("position"), e["data"].get("outcome"))
        for e in events
        if e["event"] in {"plan_step_finished", "plan_finished"}
    ]
    # A Stop skips the step it stopped (ticket 06); it did not fail.
    assert tail == [
        ("plan_step_finished", 1, "skipped"),
        ("plan_step_finished", 2, "skipped"),
        ("plan_finished", None, "cancelled"),
    ]
    assert len(model.requests) == 1
    # The Session is free again.
    again = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "افتح السلة", "snapshot": home_snapshot()},
    )
    assert again.status_code == 202


def test_a_plan_step_answering_with_its_own_later_steps_never_nests_a_plan():
    nested = intent("checkout", remaining_steps=["افتح الحساب"], first_step="x")
    client, model = make_client(two_steps("cart"), nested)
    session_id = start(client)
    first = stream(client, session_id)
    complete(client, session_id, first, "/cart")
    second = stream(client, session_id)
    complete(client, session_id, second, "/checkout")
    events = stream(client, session_id)
    assert names(events).count("plan_created") == 1
    assert names(events).count("task_started") == 2
    assert len(model.requests) == 2
    assert names(events)[-1] == "plan_finished"


def test_an_answer_to_step_one_that_repeats_the_steps_does_not_create_a_second_plan():
    asking = two_steps("cart", needs_clarification=True, missing_fields=["target"])
    client, _ = make_client(asking, two_steps("cart"), intent("checkout"))
    session_id = start(client)
    question = last_action(stream(client, session_id))
    client.post(
        f"/sessions/{session_id}/tasks/{question['task_id']}/answers",
        json={"question_id": question["action_id"], "text": "السلة", "snapshot": home_snapshot()},
    )
    assert names(stream(client, session_id)).count("plan_created") == 1


# --- Event-log records ------------------------------------------------------------------


def test_plan_records_have_fixed_fields_and_no_shopper_or_step_text():
    sink = MemorySink()
    client, _ = make_client(two_steps("cart"), intent("checkout"), sink=sink)
    session_id = start(client)
    run_two_steps(client, session_id)

    records = [r for r in sink.records if r["event"].startswith("plan_")]
    by_event = {}
    for record in records:
        by_event.setdefault(record["event"], []).append(record)
    plan_id = by_event["plan_created"][0]["plan_id"]
    created = by_event["plan_created"][0]
    assert {k: created[k] for k in ("plan_id", "step_count", "skipped_count")} == {
        "plan_id": plan_id,
        "step_count": 2,
        "skipped_count": 0,
    }
    assert (created["language"], created["dialect"]) == ("ar", "egyptian_arabic")
    steps = by_event["plan_step"]
    assert [
        (r["plan_id"], r["position"], r["outcome"], r["intent_type"], r["guarded"]) for r in steps
    ] == [
        (plan_id, 1, "done", "navigate", False),
        (plan_id, 2, "done", "navigate", False),
    ]
    finished = by_event["plan_finished"][0]
    assert (finished["outcome"], finished["done_count"]) == ("done", 2)
    assert (finished["failed_count"], finished["skipped_count"]) == (0, 0)

    allowed = {
        "plan_created": {"plan_id", "step_count", "skipped_count", "language", "dialect"},
        "plan_step": {"plan_id", "position", "outcome", "intent_type", "guarded"},
        "plan_finished": {"plan_id", "outcome", "done_count", "failed_count", "skipped_count"},
    }
    common = {"time", "release", "event", "session_id", "shopper", "invitation_id", "task_id"}
    for record in records:
        assert set(record) - common <= allowed[record["event"]]
    dumped = json.dumps(sink.records, ensure_ascii=False)
    for private in (SHOPPER_TEXT, STEP_TWO, STEP_ONE_WORDS, "الدفع", "الجزمة"):
        assert private not in dumped
    # Plan events are not also written as generic task records.
    assert not [r for r in sink.records if r["event"] == "task" and r["kind"].startswith("plan_")]


def test_a_failed_plan_records_counts_and_skipped_steps():
    sink = MemorySink()
    asking = two_steps("cart", needs_clarification=True, missing_fields=["target"])
    client, _ = make_client(asking, "no", "no", sink=sink)
    session_id = start(client)
    question = last_action(stream(client, session_id))
    client.post(
        f"/sessions/{session_id}/tasks/{question['task_id']}/answers",
        json={"question_id": question["action_id"], "text": "السلة", "snapshot": home_snapshot()},
    )
    finished = next(r for r in sink.records if r["event"] == "plan_finished")
    assert (finished["outcome"], finished["done_count"]) == ("failed", 0)
    assert (finished["failed_count"], finished["skipped_count"]) == (1, 1)
    steps = [r for r in sink.records if r["event"] == "plan_step"]
    assert [(r["position"], r["outcome"]) for r in steps] == [(1, "failed"), (2, "skipped")]
    assert "intent_type" not in steps[1]


# --- Retrieval ON --------------------------------------------------------------------------


def retrieval_client(*replies, sink=None):
    return make_client(
        *replies, sink=sink, catalogue_client=Reads(), catalogue_retrieval_enabled=True
    )


def test_a_search_decision_carrying_later_steps_creates_the_plan_and_runs_step_two_after_it():
    client, model = retrieval_client(
        {
            "kind": "search",
            "query": {"query": "running shoes"},
            "first_step": "find running shoes",
            "remaining_steps": [STEP_TWO],
        },
        {"kind": "recommend", "language": "en", "selected_ids": ["p-4"]},
        advice("A light running shoe.", ["p-4"]),
        intent("checkout", language="en", dialect="english"),
    )
    session_id = start(client, "find running shoes then " + STEP_TWO)
    events = stream(client, session_id)
    created = next(e["data"] for e in events if e["event"] == "plan_created")
    assert created["steps"] == [
        {"position": 1, "text": "find running shoes"},
        {"position": 2, "text": STEP_TWO},
    ]
    # Step 1 is the catalogue task: it completed with its cards before step 2 began.
    order = names(events, PLAN_EVENTS | {"suggestions", "done", "task_started", "action"})
    assert order == [
        "task_started",
        "plan_created",
        "plan_step_started",
        "suggestions",
        "done",
        "plan_step_finished",
        "task_started",
        "plan_step_started",
        "action",
    ]
    assert model.requests[-1].messages[-1].content == STEP_TWO
    assert last_action(events)["url"] == "/checkout"
    complete(client, session_id, events, "/checkout")
    final = stream(client, session_id)
    assert names(final)[-1] == "plan_finished"
    assert [e["data"]["outcome"] for e in final if e["event"] == "plan_step_finished"] == [
        "done",
        "done",
    ]


def test_an_execute_decision_takes_the_steps_from_the_intent_call():
    client, model = retrieval_client(
        {"kind": "execute"},
        two_steps("cart"),
        {"kind": "execute"},
        intent("checkout"),
    )
    session_id = start(client)
    events = stream(client, session_id)
    assert names(events, PLAN_EVENTS) == ["plan_created", "plan_step_started"]
    created = next(e["data"] for e in events if e["event"] == "plan_created")
    assert [s["text"] for s in created["steps"]] == [STEP_ONE_WORDS, STEP_TWO]
    complete(client, session_id, events, "/cart")
    second = stream(client, session_id)
    assert last_action(second)["url"] == "/checkout"
    assert len(model.requests) == 4  # step 2 went through the decision loop again


def test_a_retrieval_step_never_nests_a_plan_from_its_own_decisions():
    client, _ = retrieval_client(
        {"kind": "execute"},
        two_steps("cart"),
        {"kind": "execute"},
        intent("checkout", remaining_steps=["افتح الحساب"], first_step="y"),
    )
    session_id = start(client)
    events = stream(client, session_id)
    complete(client, session_id, events, "/cart")
    events = stream(client, session_id)
    assert names(events).count("plan_created") == 1
    assert names(events).count("task_started") == 2


def test_a_one_step_retrieval_message_makes_the_same_calls_and_no_plan():
    client, model = retrieval_client({"kind": "execute"}, intent("cart"))
    session_id = start(client, "افتح السلة")
    events = stream(client, session_id)
    assert len(model.requests) == 2
    assert not PLAN_EVENTS & set(names(events))


# --- Decision models -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "decision",
    [
        {"kind": "search", "query": {"query": "shoes"}},
        {"kind": "details", "query": {"ids": ["p-1"]}},
        {"kind": "recommend", "language": "en", "selected_ids": []},
        {"kind": "clarify", "language": "en", "question": "Which?"},
    ],
)
def test_every_talking_decision_takes_the_step_fields_and_normalises_overflow(decision):
    parsed = DECISION.validate_python(
        {
            **decision,
            "first_step": "one",
            "remaining_steps": ["two", "three", "four"],
            "skipped_steps": None,
        }
    )
    assert parsed.first_step == "one"
    assert parsed.remaining_steps == ["two", "three"]
    assert parsed.skipped_steps == ["four"]


def test_decision_overflow_keeps_spoken_order_and_truncates_skipped():
    parsed = DECISION.validate_python(
        {
            "kind": "clarify",
            "language": "en",
            "question": "Which?",
            "remaining_steps": ["r1", "r2", "o1", "o2"],
            "skipped_steps": ["s1", "s2", "s3", "s4", "s5"],
        }
    )
    assert parsed.skipped_steps == ["o1", "o2", "s1", "s2", "s3", "s4"]


def test_execute_keeps_ignoring_extras_and_step_fields_default_to_empty():
    execute = DECISION.validate_python(
        {"kind": "execute", "remaining_steps": ["x"], "first_step": "y"}
    )
    assert not hasattr(execute, "remaining_steps")
    plain = DECISION.validate_python({"kind": "search", "query": {"query": "shoes"}})
    assert (plain.first_step, plain.remaining_steps, plain.skipped_steps) == (None, [], [])


def test_decision_step_words_must_be_plain_non_empty_strings():
    with pytest.raises(ValidationError):
        DECISION.validate_python(
            {"kind": "clarify", "language": "en", "question": "Q", "remaining_steps": [{"a": 1}]}
        )


def test_the_provider_decision_schema_stays_small_plain_strings_without_descriptions():
    from agent.llm.provider_schema import openrouter_response_schema

    schema = openrouter_response_schema(MODEL_DECISION.json_schema())
    text = json.dumps(schema)
    assert "Shopper" not in text  # no field descriptions were added for the step fields
    branch = next(b for b in schema["oneOf"] if b["properties"]["kind"]["enum"] == ["clarify"])
    assert branch["properties"]["remaining_steps"] == {"items": {"type": "string"}, "type": "array"}
    assert "title" not in branch["properties"]["first_step"]
    # 8880 bytes before `beneficiary` (nullable, one enum per branch) joined the four branches.
    assert len(text.encode()) < 10000


def run_retrieval(model):
    return retrieve_products(
        "do it",
        {},
        model,
        Reads(),
        active,
        storefront=ScriptedPlanner().storefront,
        budget=RetrievalBudget(),
    )


def test_the_first_decision_naming_later_steps_wins_for_the_outcome():
    import asyncio

    model = RecordingModel(
        {
            "kind": "search",
            "query": {"query": "shoes"},
            "first_step": "a",
            "remaining_steps": ["b"],
        },
        {
            "kind": "search",
            "query": {"query": "shoes"},
            "first_step": "z",
            "remaining_steps": ["y"],
        },
        {"kind": "recommend", "language": "en", "selected_ids": ["p-4"]},
    )
    outcome = asyncio.run(run_retrieval(model))
    assert (outcome.first_step, outcome.remaining_steps, outcome.skipped_steps) == ("a", ["b"], [])


def test_a_later_decision_may_name_the_steps_when_the_first_did_not():
    import asyncio

    model = RecordingModel(
        {"kind": "search", "query": {"query": "shoes"}},
        {
            "kind": "recommend",
            "language": "en",
            "selected_ids": ["p-4"],
            "first_step": "shoes",
            "remaining_steps": ["b", "c", "d"],
        },
    )
    outcome = asyncio.run(run_retrieval(model))
    assert (outcome.first_step, outcome.remaining_steps, outcome.skipped_steps) == (
        "shoes",
        ["b", "c"],
        ["d"],
    )


def test_the_decision_prompt_asks_for_the_first_step_only_and_is_v9():
    import asyncio

    model = RecordingModel({"kind": "clarify", "language": "en", "question": "Which one?"})
    asyncio.run(run_retrieval(model))
    request = model.requests[0]
    assert request.prompt_version == "catalogue-decision-v11"
    for phrase in ("first_step", "remaining_steps", "FIRST step only", "skipped_steps"):
        assert phrase in request.system


def test_the_sent_provider_schema_requires_the_step_fields_but_the_models_still_default():
    request = RecordingModel({"kind": "clarify", "language": "en", "question": "Which?"})
    import asyncio

    asyncio.run(run_retrieval(request))
    sent = request.requests[0].response_schema
    required = {
        branch["properties"]["kind"]["enum"][0]: branch["required"]
        for branch in __import__(
            "agent.llm.provider_schema", fromlist=["x"]
        ).openrouter_response_schema(sent)["oneOf"]
    }
    steps = ["first_step", "remaining_steps", "beneficiary"]
    assert required == {
        "search": ["kind", "query", *steps],
        "details": ["kind", "query", *steps],
        "execute": ["kind"],
        "clarify": ["kind", "question", "language", *steps],
        "recommend": ["kind", "language", "selected_ids", *steps],
    }
    # Models keep their defaults: a reply that omits the fields still parses.
    assert (
        DECISION.validate_python({"kind": "search", "query": {"query": "x"}}).remaining_steps == []
    )


def test_the_multi_part_rule_leads_the_decision_prompt_once_with_both_examples():
    import asyncio

    model = RecordingModel({"kind": "clarify", "language": "en", "question": "Which?"})
    asyncio.run(run_retrieval(model))
    system = model.requests[0].system
    assert system.startswith("FIRST RULE")
    assert system.count("FIRST step only") == 1
    assert "open the cart" in system and "افتحلي العربية" in system


def test_a_step_that_ends_in_the_exhausted_fallback_fails_and_skips_everything_after_it():
    sink = MemorySink()
    client, model = retrieval_client(
        {"kind": "execute"},
        intent(
            "cart", first_step="open the cart", remaining_steps=["show me bags", "open checkout"]
        ),
        {},
        {},
        {},
        sink=sink,
    )
    session_id = start(client, "open the cart, show me bags, then open checkout")
    events = stream(client, session_id)
    complete(client, session_id, events, "/cart")
    events = stream(client, session_id)
    # The Shopper still sees the ordinary fallback answer for the step.
    summaries = [e["data"]["summary"] for e in events if e["event"] == "done"]
    assert "couldn't finish this search" in summaries[-1] or "ما قدرتش" in summaries[-1]
    tail = [
        (e["data"]["position"], e["data"]["outcome"])
        for e in events
        if e["event"] == "plan_step_finished"
    ]
    assert tail == [(1, "done"), (2, "failed"), (3, "skipped")]
    assert names(events)[-1] == "plan_finished"
    assert [e["data"]["outcome"] for e in events if e["event"] == "plan_finished"] == ["failed"]
    assert names(events).count("task_started") == 2  # step 3 never started
    finished = next(r for r in sink.records if r["event"] == "plan_finished")
    assert (finished["done_count"], finished["failed_count"], finished["skipped_count"]) == (
        1,
        1,
        1,
    )


# --- A later step knows the earlier parts are finished -----------------------------------


def request_context(request):
    """The JSON context object the intent request carries at the start of its system text."""
    return json.loads(request.system.split("\n", 1)[0].split("context: ", 1)[1])


def test_a_later_step_request_carries_the_plan_step_marker_and_the_first_does_not():
    client, model = make_client(two_steps("cart"), intent("checkout"))
    session_id = start(client)
    first = stream(client, session_id)
    complete(client, session_id, first, "/cart")
    first_state = request_context(model.requests[0])["resolved_state"]
    second_state = request_context(model.requests[1])["resolved_state"]
    assert "_plan_step" not in first_state
    assert second_state["_plan_step"] == {"position": 2, "of": 2, "earlier_steps_done": True}
    # The step's own words are the original message the quote guard checks against.
    assert second_state["_original_message"] == STEP_TWO
    assert "plan_step" in model.requests[1].system  # the intent prompt explains the marker


def test_the_catalogue_decision_request_carries_the_marker_for_a_later_step():
    client, model = retrieval_client(
        {
            "kind": "search",
            "query": {"query": "running shoes"},
            "first_step": "find running shoes",
            "remaining_steps": ["show me bags"],
        },
        {"kind": "recommend", "language": "en", "selected_ids": ["p-4"]},
        advice("A light running shoe.", ["p-4"]),
        # Step 2 goes straight to the intent call (products are known), which is also marked.
        intent("cart", language="en", dialect="english"),
    )
    session_id = start(client, "find running shoes then show me bags")
    stream(client, session_id)
    first = json.loads(model.requests[0].messages[0].content)
    assert "plan_step" not in first or first["plan_step"] is None
    step_two = model.requests[-1]
    assert request_context(step_two)["resolved_state"]["_plan_step"]["position"] == 2


def test_a_decision_request_for_a_later_step_includes_the_marker_and_the_rule():
    client, model = retrieval_client(
        {"kind": "execute"},
        two_steps("cart"),
        {"kind": "clarify", "language": "en", "question": "Which bag?"},
    )
    session_id = start(client)
    first = stream(client, session_id)
    complete(client, session_id, first, "/cart")
    decision_request = model.requests[2]
    context = json.loads(decision_request.messages[0].content)
    assert context["plan_step"] == {"position": 2, "of": 2, "earlier_steps_done": True}
    assert "plan_step" in decision_request.system
    assert "plan_step" not in json.loads(model.requests[0].messages[0].content) or (
        json.loads(model.requests[0].messages[0].content)["plan_step"] is None
    )


def test_a_later_step_cannot_navigate_by_quoting_an_earlier_steps_words():
    # Seen live: step 2 "find me a black backpack" was answered with step 1's "open the cart".
    repeated = intent("cart", navigation_source=STEP_ONE_WORDS)
    client, model = make_client(two_steps("cart"), repeated, repeated)
    session_id = start(client)
    first = stream(client, session_id)
    complete(client, session_id, first, "/cart")
    events = stream(client, session_id)
    assert [e["data"]["outcome"] for e in events if e["event"] == "plan_step_finished"] == [
        "done",
        "failed",
    ]
    navigations = [
        e["data"]["action"]["url"]
        for e in events
        if e["event"] == "action" and e["data"]["action"]["type"] == "navigate"
    ]
    assert navigations == ["/cart"]  # step 1 only; step 2 never navigated
    assert len(model.requests) == 3  # step 1, then step 2 and its one repair


def test_a_later_step_navigates_when_its_quote_is_its_own_words():
    client, _ = make_client(two_steps("cart"), intent("checkout", navigation_source=STEP_TWO))
    session_id = start(client)
    events = run_two_steps(client, session_id)
    assert [e["data"]["outcome"] for e in events if e["event"] == "plan_finished"] == ["done"]


def test_a_later_step_cannot_reuse_the_whole_original_message_as_its_quote():
    repeated = intent(
        "cart",
        intent="cart_edit",
        constraints={},
        cart_operation="remove",
        cart_source=SHOPPER_TEXT,
    )
    client, model = make_client(two_steps("cart"), repeated, repeated)
    session_id = start(client)
    first = stream(client, session_id)
    complete(client, session_id, first, "/cart")
    events = stream(client, session_id)
    assert [e["data"]["outcome"] for e in events if e["event"] == "plan_step_finished"] == [
        "done",
        "failed",
    ]
    assert not [e for e in events if e["event"] == "action" and "remove" in str(e)]
    assert [e["data"]["outcome"] for e in events if e["event"] == "plan_finished"] == ["failed"]
