"""Product identity and conversational continuity through the live HTTP boundary."""

import json

import pytest

from agent.app import create_app
from agent.catalogue import CatalogueSnapshot
from agent.llm import LLMChunk, LLMSettings
from agent.tests.http_client import TestClient
from agent.tests.test_cart_conversation_repair import cart_snapshot
from agent.tests.test_catalogue import catalogue
from agent.tests.test_real_task import action_result, snapshot_at
from agent.tests.test_sessions import parse_sse


def decision(kind, **fields):
    return dict(
        v=8,
        language="en",
        dialect="english",
        intent=kind,
        constraints={},
        missing_fields=[],
        needs_clarification=False,
        **fields,
    )


class Model:
    def __init__(self, *decisions):
        self.decisions = iter(decisions)
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        yield LLMChunk(text=json.dumps(next(self.decisions)))


def events(client, sid):
    response = client.get(f"/sessions/{sid}/events?once=true&tab_id=tab-local")
    assert response.status_code == 200
    return parse_sse(response.text)


def actions(client, sid):
    return [e["data"]["action"] for e in events(client, sid) if e["event"] == "action"]


def submit(client, sid, message, snapshot):
    result = client.post(
        f"/sessions/{sid}/messages",
        json={"text": message, "snapshot": snapshot},
        headers={"X-Tab-Id": "tab-local"},
    )
    assert result.status_code == 202


def report(client, sid, snapshot, status="navigated"):
    result = action_result(actions(client, sid)[-1], snapshot)
    result["status"] = status
    assert (
        client.post(
            f"/sessions/{sid}/action-results", json=result, headers={"X-Tab-Id": "tab-local"}
        ).status_code
        == 202
    )


@pytest.mark.parametrize("href", ["/p/clothing-05", "http://localhost:4000/p/clothing-05"])
def test_visible_cart_product_can_open_without_prior_recommendations(href):
    model = Model(decision("open_product", product_id="clothing-05"))
    with TestClient(
        create_app(llm_settings=LLMSettings(provider="groq", model="test"), llm_client=model)
    ) as client:
        sid = client.post("/sessions").json()["session_id"]
        current = snapshot_at(
            "/cart", dict(id=22, role="link", name="قميص رسمي", href=href, visible=True)
        )
        submit(client, sid, "وديني لصفحة قميص رسمي تاني كده", current)
        assert [a["url"] for a in actions(client, sid)] == ["/p/clothing-05"]


@pytest.mark.parametrize(
    "link",
    [
        dict(href="https://evil.example/p/clothing-05", visible=True),
        dict(href="/p/clothing-05", visible=False),
        dict(href="/p/clothing-05", visible=True, disabled=True),
        dict(href="/p/../checkout", visible=True),
    ],
)
def test_untrusted_or_unavailable_product_link_does_not_authorize_navigation(link):
    proposed = decision("open_product", product_id="clothing-05")
    model = Model(proposed, proposed)
    with TestClient(
        create_app(llm_settings=LLMSettings(provider="groq", model="test"), llm_client=model)
    ) as client:
        sid = client.post("/sessions").json()["session_id"]
        submit(
            client,
            sid,
            "open shirt",
            snapshot_at("/cart", dict(id=22, role="link", name="Shirt", **link)),
        )
        assert actions(client, sid) == []


@pytest.mark.parametrize("intervening", ["navigate", "cart_edit", "find_products"])
def test_verified_product_survives_other_tasks_and_refresh(intervening):
    class Reader:
        def __init__(self):
            self.index = 0

        async def read(self):
            product = catalogue().products[-1 if self.index == 0 else 2]
            self.index += 1
            return CatalogueSnapshot(v=1, currency="EGP", products=[product])

    recommend = decision("find_products", request_mode="recommend")
    recommend["constraints"] = {"category": "clothing"}
    middle = decision(intervening)
    if intervening == "navigate":
        middle["constraints"] = {"target": "cart"}
    elif intervening == "cart_edit":
        middle.update(
            cart_operation="quantity",
            cart_target_id=13,
            cart_quantity=3,
            cart_quantity_mode="increase",
            cart_source="Do another shopping task",
        )
    else:
        middle.update(request_mode="recommend", constraints={"category": "shoes"})
    model = Model(
        recommend,
        decision("open_product", product_id="white-shirt"),
        middle,
        decision("open_product", product_id="white-shirt"),
    )
    with TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="test"),
            llm_client=model,
            catalogue_reader=Reader(),
        )
    ) as client:
        sid = client.post("/sessions").json()["session_id"]
        submit(client, sid, "Recommend a shirt for the outfit", snapshot_at("/"))
        submit(client, sid, "Open the white shirt", snapshot_at("/"))
        heading = dict(id=1, role="heading", level=1, name="White Shirt", visible=True)
        report(client, sid, snapshot_at("/p/white-shirt", heading))
        current = cart_snapshot(3) if intervening == "cart_edit" else snapshot_at("/")
        submit(client, sid, "Do another shopping task", current)
        if intervening == "navigate":
            report(client, sid, snapshot_at("/cart"))
        elif intervening == "cart_edit":
            current["elements"][2]["value"] = "4"
            report(client, sid, current, "ok")
            current["elements"].append(
                dict(id=99, role="status", name="تم تحديث الكمية", visible=True)
            )
            report(client, sid, current, "ok")
        # A refresh and a page without product links must not erase verified history.
        client.get(f"/sessions/{sid}/state?tab_id=tab-local")
        reconciled = client.post(
            f"/sessions/{sid}/reconcile",
            headers={"X-Tab-Id": "tab-local"},
            json={"tab_id": "tab-local", "snapshot": snapshot_at("/")},
        )
        assert reconciled.status_code == 200
        before = len(actions(client, sid))
        submit(client, sid, "Open the white shirt from earlier again", snapshot_at("/"))
        new = actions(client, sid)[before:]
        assert [a["url"] for a in new] == ["/p/white-shirt"]
        assert '"known_products"' in model.requests[-1].system
    assert any(
        "Recommend a shirt for the outfit" in message.content
        for message in model.requests[-1].messages[:-1]
    )


@pytest.mark.parametrize("observation", ["action_result", "reconcile"])
def test_browsed_product_identity_survives_leaving_the_results_page(observation):
    browse = decision("find_products")
    browse["constraints"] = {"category": "clothing"}
    model = Model(browse, decision("open_product", product_id="clothing-05"))
    with TestClient(
        create_app(llm_settings=LLMSettings(provider="groq", model="test"), llm_client=model)
    ) as client:
        sid = client.post("/sessions").json()["session_id"]
        submit(client, sid, "Browse shirts", snapshot_at("/"))
        listing = snapshot_at(
            "/c/clothing",
            dict(
                id=7,
                role="link",
                name="قميص رسمي",
                group="قميص رسمي / Formal Shirt",
                href="/p/clothing-05",
                visible=True,
            ),
            dict(
                id=8,
                role="link",
                name="عرض التفاصيل",
                group="قميص رسمي / Formal Shirt",
                href="/p/clothing-05",
                visible=True,
            ),
        )
        report(
            client, sid, listing if observation == "action_result" else snapshot_at("/c/clothing")
        )
        if observation == "reconcile":
            assert (
                client.post(
                    f"/sessions/{sid}/reconcile",
                    headers={"X-Tab-Id": "tab-local"},
                    json={"tab_id": "tab-local", "snapshot": listing},
                ).status_code
                == 200
            )
        submit(client, sid, "Open the Formal Shirt I saw earlier", snapshot_at("/cart"))
        assert actions(client, sid)[-1]["url"] == "/p/clothing-05"
        context = json.loads(model.requests[-1].system.split("\n", 1)[0].split(": ", 1)[1])
        assert context["known_products"] == [
            {"id": "clothing-05", "name": "قميص رسمي / Formal Shirt"}
        ]


@pytest.mark.parametrize("change", ["session", "origin"])
def test_remembered_identity_does_not_cross_session_or_origin(change):
    opening = decision("open_product", product_id="clothing-05")
    model = Model(opening, opening, opening)
    with TestClient(
        create_app(llm_settings=LLMSettings(provider="groq", model="test"), llm_client=model)
    ) as client:
        sid = client.post("/sessions").json()["session_id"]
        submit(
            client,
            sid,
            "Open the Shirt, original conversation",
            snapshot_at(
                "/cart", dict(id=22, role="link", name="Shirt", href="/p/clothing-05", visible=True)
            ),
        )
        report(client, sid, snapshot_at("/p/clothing-05"))
        if change == "session":
            sid = client.post("/sessions").json()["session_id"]
        current = snapshot_at("/")
        if change == "origin":
            current["url"] = "https://other.example/"
        before = 0 if change == "session" else len(actions(client, sid))
        submit(client, sid, "Open the earlier Shirt", current)
        assert len(actions(client, sid)) == before
        context = json.loads(model.requests[-1].system.split("\n", 1)[0].split(": ", 1)[1])
        assert context["known_products"] == []
    assert len(model.requests[-1].messages) == 1


@pytest.mark.parametrize("continuation", ["answer", "retry"])
def test_origin_change_cannot_resume_an_old_task_or_send_its_context(continuation):
    opening = decision("open_product", product_id="clothing-05")
    question = {
        **opening,
        "product_id": None,
        "needs_clarification": True,
        "missing_fields": ["product_id"],
    }
    invalid = {**opening, "product_id": "unknown-product"}
    model = (
        Model(question, opening) if continuation == "answer" else Model(invalid, invalid, opening)
    )
    with TestClient(
        create_app(llm_settings=LLMSettings(provider="groq", model="test"), llm_client=model)
    ) as client:
        sid = client.post("/sessions").json()["session_id"]
        submit(
            client,
            sid,
            "Open that product",
            snapshot_at(
                "/cart",
                dict(
                    id=22, role="link", name="Original Shirt", href="/p/clothing-05", visible=True
                ),
            ),
        )
        task = client.get(f"/sessions/{sid}/state?tab_id=tab-local").json()["task"]
        foreign = {**snapshot_at("/"), "url": "https://other.example/"}
        assert (
            client.post(
                f"/sessions/{sid}/reconcile",
                json={"snapshot": foreign},
                headers={"X-Tab-Id": "tab-local"},
            ).status_code
            == 200
        )
        before = len(model.requests)
        if continuation == "answer":
            path, body = (
                "answers",
                {
                    "question_id": task["pending_question"]["action_id"],
                    "text": "Original Shirt",
                    "snapshot": foreign,
                },
            )
        else:
            path, body = "retry", {"snapshot": foreign}
        result = client.post(
            f"/sessions/{sid}/tasks/{task['task_id']}/{path}",
            json=body,
            headers={"X-Tab-Id": "tab-local"},
        )
        assert result.status_code == 409
        assert len(model.requests) == before


def test_product_memory_preserves_both_variant_labels_instead_of_only_the_last():
    model = Model(decision("help"))
    with TestClient(
        create_app(llm_settings=LLMSettings(provider="groq", model="test"), llm_client=model)
    ) as client:
        sid = client.post("/sessions").json()["session_id"]
        current = snapshot_at(
            "/cart",
            dict(
                id=1,
                role="link",
                name="Shirt",
                group="Shirt M white",
                href="/p/shirt",
                visible=True,
            ),
            dict(
                id=2,
                role="link",
                name="Shirt",
                group="Shirt L white",
                href="/p/shirt",
                visible=True,
            ),
        )
        submit(client, sid, "hello", current)
        context = json.loads(model.requests[-1].system.split("\n", 1)[0].split(": ", 1)[1])
        assert len(context["known_products"]) == 1
        assert "Shirt M white" in context["known_products"][0]["name"]
        assert "Shirt L white" in context["known_products"][0]["name"]
