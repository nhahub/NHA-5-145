from agent.app import create_app
from agent.planner import snapshot_matches_url
from agent.schemas import Snapshot
from agent.tests.http_client import TestClient
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot


def test_discovery_uses_applied_results_not_draft_controls_or_address_bar():
    page = {
        **home_snapshot(),
        "url": "http://localhost:4000/c/shoes?max_price=2000",
        "elements": [
            dict(id=1, role="link", name="النتائج الحالية", href="/c/shoes", visible=True)
        ],
    }
    assert not snapshot_matches_url(Snapshot.model_validate(page), "/c/shoes?max_price=2000")
    page["url"] = "http://localhost:4000/c/shoes"
    page["elements"][0]["href"] = "/c/shoes?max_price=2000"
    assert snapshot_matches_url(Snapshot.model_validate(page), "/c/shoes?max_price=2000")
    page["elements"][0]["href"] = "https://attacker.example/c/shoes?max_price=2000"
    assert not snapshot_matches_url(Snapshot.model_validate(page), "/c/shoes?max_price=2000")


def test_event_stream_reconnect_resumes_after_last_delivered_event():
    with TestClient(create_app()) as client:
        sid = client.post("/sessions").json()["session_id"]
        client.post(
            f"/sessions/{sid}/messages",
            json={
                "text": "Open cart",
                "snapshot": home_snapshot(),
            },
        )
        initial = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
        resumed = parse_sse(
            client.get(
                f"/sessions/{sid}/events?once=true&after=0",
                headers={"Last-Event-ID": str(initial[-2]["id"])},
            ).text
        )
        assert resumed == initial[-1:]
        assert (
            client.get(
                f"/sessions/{sid}/events?once=true",
                headers={"Last-Event-ID": str(initial[-1]["id"])},
            ).text
            == ""
        )
