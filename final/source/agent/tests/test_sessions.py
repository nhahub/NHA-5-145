import json

from agent.app import create_app
from agent.schemas import AskShopperAction, Snapshot
from agent.sessions import SessionStore
from agent.tests.http_client import TestClient
from agent.tests.test_step import home_snapshot


def parse_sse(payload: str) -> list[dict[str, object]]:
    events = []
    for block in payload.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append(
            {
                "id": int(fields["id"]),
                "event": fields["event"],
                "data": json.loads(fields["data"]),
            }
        )
    return events


def test_session_streams_task_narration_and_action_in_order() -> None:
    client = TestClient(create_app())
    session_id = client.post("/sessions").json()["session_id"]

    submitted = client.post(
        f"/sessions/{session_id}/messages",
        json={
            "text": "عاوز كوتشي للجري بأقل من ٢٠٠٠",
            "snapshot": home_snapshot(),
        },
    )

    assert submitted.status_code == 202
    task_id = submitted.json()["task_id"]
    events = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)
    assert [event["event"] for event in events] == ["task_started", "narration", "action"]
    assert [event["id"] for event in events] == [1, 2, 3]
    assert all(event["data"]["task_id"] == task_id for event in events)
    action = events[2]["data"]["action"]
    assert action["task_id"] == task_id
    assert action["action_id"]
    assert action["sequence_number"] == 1


def test_second_task_requires_explicit_replacement() -> None:
    client = TestClient(create_app())
    session_id = client.post("/sessions").json()["session_id"]
    message = {"text": "Show me running shoes under 2000 EGP", "snapshot": home_snapshot()}

    first = client.post(f"/sessions/{session_id}/messages", json=message)
    conflict = client.post(f"/sessions/{session_id}/messages", json=message)
    replacement = client.post(
        f"/sessions/{session_id}/messages",
        json={**message, "replace_active": True},
    )

    assert first.status_code == 202
    assert conflict.status_code == 409
    assert replacement.status_code == 202
    events = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)
    assert [event["event"] for event in events] == [
        "task_started",
        "narration",
        "action",
        "cancelled",
        "task_started",
        "narration",
        "action",
    ]
    assert events[3]["data"]["task_id"] == first.json()["task_id"]
    assert replacement.json()["task_id"] != first.json()["task_id"]


def test_only_the_matching_action_result_completes_the_active_task() -> None:
    client = TestClient(create_app())
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "عاوز كوتشي للجري بأقل من ٢٠٠٠", "snapshot": home_snapshot()},
    )
    action_event = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)[
        -1
    ]
    action = action_event["data"]["action"]
    filtered_snapshot = {
        **home_snapshot(),
        "url": "http://localhost:4000/c/shoes?type=running&max_price=2000",
        "title": "الأحذية",
    }
    result = {
        "v": 1,
        "task_id": action["task_id"],
        "action_id": action["action_id"],
        "sequence_number": action["sequence_number"],
        "status": "navigated",
        "snapshot": filtered_snapshot,
    }

    mismatch = client.post(
        f"/sessions/{session_id}/action-results",
        json={**result, "action_id": "different-action"},
    )
    accepted = client.post(f"/sessions/{session_id}/action-results", json=result)

    assert mismatch.status_code == 409
    assert accepted.status_code == 202
    completion = parse_sse(client.get(f"/sessions/{session_id}/events?after=3&once=true").text)
    assert [event["event"] for event in completion] == ["done"]
    assert completion[-1]["data"]["task_id"] == action["task_id"]


def test_duplicate_action_result_is_acknowledged_without_repeating_events() -> None:
    client = TestClient(create_app())
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "عاوز كوتشي للجري بأقل من ٢٠٠٠", "snapshot": home_snapshot()},
    )
    action = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)[-1][
        "data"
    ]["action"]
    result = {
        "v": 1,
        "task_id": action["task_id"],
        "action_id": action["action_id"],
        "sequence_number": action["sequence_number"],
        "status": "navigated",
        "snapshot": {
            **home_snapshot(),
            "url": "http://localhost:4000/c/shoes?type=running&max_price=2000",
        },
    }

    first = client.post(f"/sessions/{session_id}/action-results", json=result)
    duplicate = client.post(f"/sessions/{session_id}/action-results", json=result)
    conflicting_duplicate = client.post(
        f"/sessions/{session_id}/action-results",
        json={**result, "status": "blocked"},
    )

    assert first.status_code == 202
    assert duplicate.status_code == 202
    assert conflicting_duplicate.status_code == 409
    assert duplicate.json() == {"task_id": action["task_id"], "status": "accepted"}
    completion = parse_sse(client.get(f"/sessions/{session_id}/events?after=3&once=true").text)
    assert [event["event"] for event in completion] == ["done"]


def test_stop_cancels_the_active_task_and_rejects_its_later_result() -> None:
    client = TestClient(create_app())
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "عاوز كوتشي للجري بأقل من ٢٠٠٠", "snapshot": home_snapshot()},
    )
    action = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)[-1][
        "data"
    ]["action"]

    stopped = client.post(f"/sessions/{session_id}/stop")
    later_result = client.post(
        f"/sessions/{session_id}/action-results",
        json={
            "v": 1,
            "task_id": action["task_id"],
            "action_id": action["action_id"],
            "sequence_number": action["sequence_number"],
            "status": "navigated",
            "snapshot": {**home_snapshot(), "url": f"http://localhost:4000{action['url']}"},
        },
    )

    assert stopped.status_code == 202
    assert later_result.status_code == 409
    events = parse_sse(client.get(f"/sessions/{session_id}/events?after=3&once=true").text)
    assert [event["event"] for event in events] == ["cancelled"]


def test_failed_action_result_reports_failure_without_completing_the_task() -> None:
    client = TestClient(create_app())
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "عاوز كوتشي للجري بأقل من ٢٠٠٠", "snapshot": home_snapshot()},
    )
    action = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)[-1][
        "data"
    ]["action"]

    accepted = client.post(
        f"/sessions/{session_id}/action-results",
        json={
            "v": 1,
            "task_id": action["task_id"],
            "action_id": action["action_id"],
            "sequence_number": action["sequence_number"],
            "status": "blocked",
            "snapshot": home_snapshot(),
        },
    )

    assert accepted.status_code == 202
    events = parse_sse(client.get(f"/sessions/{session_id}/events?after=3&once=true").text)
    assert [event["event"] for event in events] == ["narration", "action"]
    question = events[-1]["data"]["action"]
    assert question["type"] == "ask_shopper"
    assert "ماذا تريد" in question["question"]


def test_matching_answer_resumes_the_same_paused_task() -> None:
    client = TestClient(create_app())
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={
            "text": "Show me running shoes under 2000 USD",
            "snapshot": home_snapshot(),
        },
    )
    question = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)[-1][
        "data"
    ]["action"]

    mismatch = client.post(
        f"/sessions/{session_id}/tasks/{question['task_id']}/answers",
        json={
            "question_id": "different-question",
            "text": "2000 EGP",
            "snapshot": home_snapshot(),
        },
    )
    answered = client.post(
        f"/sessions/{session_id}/tasks/{question['task_id']}/answers",
        json={
            "question_id": question["action_id"],
            "text": "2000 EGP",
            "snapshot": home_snapshot(),
        },
    )

    assert mismatch.status_code == 409
    assert answered.status_code == 202
    resumed = parse_sse(client.get(f"/sessions/{session_id}/events?after=3&once=true").text)
    assert [event["event"] for event in resumed] == ["narration", "action"]
    assert resumed[-1]["data"]["action"]["task_id"] == question["task_id"]
    assert resumed[-1]["data"]["action"]["sequence_number"] == 2


def test_stop_while_waiting_for_answer_rejects_later_answer() -> None:
    client = TestClient(create_app())
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Show me running shoes under 2000 USD", "snapshot": home_snapshot()},
    )
    question = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)[-1][
        "data"
    ]["action"]

    stopped = client.post(f"/sessions/{session_id}/stop")
    late_answer = client.post(
        f"/sessions/{session_id}/tasks/{question['task_id']}/answers",
        json={
            "question_id": question["action_id"],
            "text": "2000 EGP",
            "snapshot": home_snapshot(),
        },
    )

    assert stopped.status_code == 202
    assert late_answer.status_code == 409
    events = parse_sse(client.get(f"/sessions/{session_id}/events?after=3&once=true").text)
    assert [event["event"] for event in events] == ["cancelled"]


def test_eight_step_cap_pauses_for_shopper_direction() -> None:
    store = SessionStore()
    session = store.create()
    snapshot = Snapshot.model_validate(home_snapshot())
    task = store.submit_message(
        session.session_id,
        "Show me running shoes under 2000 USD",
        snapshot,
    )
    task.step_count = 8

    paused = store.answer(
        session.session_id,
        task.task_id,
        task.action.action_id,
        "2000 EGP",
        snapshot,
    )

    assert isinstance(paused.action, AskShopperAction)
    assert "step limit" in paused.action.question.lower()
    assert paused.status == "awaiting_answer"


def test_english_task_completion_remains_in_english() -> None:
    client = TestClient(create_app())
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Show me running shoes under 2000 EGP", "snapshot": home_snapshot()},
    )
    action = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)[-1][
        "data"
    ]["action"]
    client.post(
        f"/sessions/{session_id}/action-results",
        json={
            "v": 1,
            "task_id": action["task_id"],
            "action_id": action["action_id"],
            "sequence_number": action["sequence_number"],
            "status": "navigated",
            "snapshot": {
                **home_snapshot(),
                "url": f"http://localhost:4000{action['url']}",
                "elements": [
                    {"id": 1, "role": "heading", "name": "3 منتجات", "level": 2, "visible": True}
                ],
            },
        },
    )

    events = parse_sse(client.get(f"/sessions/{session_id}/events?after=3&once=true").text)
    assert [event["event"] for event in events] == ["narration", "done"]
    assert events[0]["data"]["text"] == "The filters were applied successfully."
    assert events[1]["data"]["summary"] == "Matching products are now shown."


def test_other_discovery_tasks_use_a_generic_completion_summary() -> None:
    client = TestClient(create_app())
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Show unavailable bags newest first", "snapshot": home_snapshot()},
    )
    action = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)[-1][
        "data"
    ]["action"]
    client.post(
        f"/sessions/{session_id}/action-results",
        json={
            "v": 1,
            "task_id": action["task_id"],
            "action_id": action["action_id"],
            "sequence_number": action["sequence_number"],
            "status": "navigated",
            "snapshot": {
                **home_snapshot(),
                "url": f"http://localhost:4000{action['url']}",
                "elements": [
                    {"id": 1, "role": "heading", "name": "3 منتجات", "level": 2, "visible": True}
                ],
            },
        },
    )

    events = parse_sse(client.get(f"/sessions/{session_id}/events?after=3&once=true").text)
    assert events[-1]["data"]["summary"] == "Matching products are now shown."


def test_navigation_with_missing_expected_state_falls_back_to_a_visible_control() -> None:
    client = TestClient(create_app())
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Show me running shoes under 2000 EGP", "snapshot": home_snapshot()},
    )
    action = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)[-1][
        "data"
    ]["action"]
    unfiltered_snapshot = {
        **home_snapshot(),
        "url": "http://localhost:4000/c/shoes",
        "elements": [
            {
                "id": 9,
                "role": "textbox",
                "name": "أقصى سعر",
                "value": "",
                "visible": True,
            }
        ],
    }

    accepted = client.post(
        f"/sessions/{session_id}/action-results",
        json={
            "v": 1,
            "task_id": action["task_id"],
            "action_id": action["action_id"],
            "sequence_number": action["sequence_number"],
            "status": "navigated",
            "snapshot": unfiltered_snapshot,
        },
    )

    assert accepted.status_code == 202
    events = parse_sse(client.get(f"/sessions/{session_id}/events?after=3&once=true").text)
    assert [event["event"] for event in events] == ["narration", "action"]
    fallback = events[-1]["data"]["action"]
    assert fallback["type"] == "type"
    assert fallback["id"] == 9
    assert fallback["text"] == "2000"
    assert fallback["submit"] is True
