"""Scripted catalogue browser fixture ONLY. It tests execution, not language accuracy."""

import json

from agent.app import create_app
from agent.catalogue_contract import SearchQuery
from agent.llm import LLMChunk, LLMSettings


def intent(name="advice", **fields):
    return {
        "v": 9,
        "language": "en",
        "dialect": "english",
        "intent": name,
        "constraints": {},
        "missing_fields": [],
        "needs_clarification": False,
        **fields,
    }


class FixtureModel:
    async def complete(self, request):
        interpreting = request.prompt_version.startswith("intent-")
        if interpreting:
            context = json.loads(request.system.split("\n", 1)[0].split(": ", 1)[1])
            context["message"] = request.messages[-1].content
        else:
            context = json.loads(request.messages[0].content)
        if request.prompt_version.startswith("advice-"):
            products = context["products"]
            response = {
                "v": 1,
                "message": "Catalogue evidence checked; unrecorded material remains unknown.",
                "product_ids": [p["id"] for p in products],
            }
        elif context["message"] == "[fixture:recommend]":
            if not context["evidence"]:
                response = {
                    "kind": "search",
                    "query": SearchQuery(
                        query="",
                        requirements=[{"field": "feature", "op": "exclude", "value": "leather"}],
                    ).model_dump(),
                }
            else:
                response = {
                    "kind": "recommend",
                    "language": "en",
                    "selected_ids": ["shoe-09"],
                    "advice_message": (
                        "Catalogue evidence checked; unrecorded material remains unknown."
                    ),
                }
        elif context["message"] == "[fixture:open]":
            response = {
                "kind": "finish",
                "intent": intent(
                    "open_product", product_id="shoe-09", navigation_source=context["message"]
                ),
                "selected_ids": [],
            }
        elif context["message"] == "[fixture:add]":
            control = next(
                e
                for e in context["current_snapshot"]["elements"]
                if e.get("form_action") == "/cart/items" and e["role"] == "button"
            )
            response = {
                "kind": "finish",
                "intent": intent(
                    "cart_edit",
                    cart_operation="add",
                    cart_target_id=control["id"],
                    cart_quantity=2,
                    cart_quantity_mode="set",
                    cart_source=context["message"],
                ),
                "selected_ids": [],
            }
        elif context["message"] == "[fixture:quantity]":
            controls = [
                e
                for e in context["current_snapshot"]["elements"]
                if e.get("form_action") == "/cart/quantity" and e["role"] == "button"
            ]
            # Explicit fixture target. No production language interpretation lives here.
            control = next(e for e in controls if "ممشى النيل" in e.get("group", ""))
            response = {
                "kind": "finish",
                "intent": intent(
                    "cart_edit",
                    cart_operation="quantity",
                    cart_target_id=control["id"],
                    cart_quantity=3,
                    cart_quantity_mode="increase",
                    cart_source=context["message"],
                ),
                "selected_ids": [],
            }
        else:
            raise ValueError("Unknown explicit fixture operation")
        if interpreting:
            response = response["intent"]
        yield LLMChunk(text=json.dumps(response, ensure_ascii=False))


app = create_app(
    llm_settings=LLMSettings(provider="groq", model="offline-fixture"),
    llm_client=FixtureModel(),
    catalogue_retrieval_enabled=True,
)
