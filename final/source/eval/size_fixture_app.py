"""Scripted remembered-sizes browser fixture ONLY. It tests memory and execution, not language.

The scripted model answers by exact message text, with realistic replies (intent v10, the
cart source quoting the message, `beneficiary`, and `constraints.size` only when the Shopper
said it). The one deliberately wrong reply is WRONG_SIZE_ADD: it carries a size nobody said.
Every model request is served at `/__eval/size-requests`; the Agent's own event records, kept
in an in-memory sink, are served at `/__eval/event-records`.
"""

import json

from agent.app import create_app
from agent.catalogue_contract import SearchQuery
from agent.event_log import MemorySink
from agent.llm import LLMChunk, LLMSettings

SHOES_43 = "عايز جزمة اكسر بيها الملعب مقاسي 43"
ADD_SHOE = "ضيفها اللون الأزرق"
TROUSERS_32 = "عايز بنطلون لاخويا مقاسه 32"
ADD_FOR_BROTHER = "ضيفه لاخويا اللون الأسود"
ADD_FOR_ME = "وضيفلي واحد ليا أنا كمان بس كاكي"
ADVICE_SHOES = "دي جزم ملعب بتناسب مقاسك."
ADVICE_TROUSERS = "دي بناطيل مناسبة لأخوك."
MESSAGES = [SHOES_43, ADD_SHOE, TROUSERS_32, ADD_FOR_BROTHER, ADD_FOR_ME]


def intent(name, **fields):
    return {
        "v": 10,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "intent": name,
        "constraints": {},
        "missing_fields": [],
        "conflicting_fields": [],
        "needs_clarification": False,
        **fields,
    }


def add_intent(context, source, constraints, beneficiary):
    control = next(
        e
        for e in context["current_snapshot"]["elements"]
        if e.get("form_action") == "/cart/items" and e["role"] == "button"
    )
    product_id = context["current_snapshot"]["url"].rsplit("/p/", 1)[1]
    return intent(
        "cart_edit",
        cart_operation="add",
        product_id=product_id,
        cart_target_id=control["id"],
        cart_quantity=1,
        cart_quantity_mode="set",
        cart_source=source,
        constraints=constraints,
        beneficiary=beneficiary,
    )


def decision(message, evidence):
    """The catalogue decision loop: one search, then a recommendation of the verified results."""
    if message == SHOES_43:
        search = SearchQuery(
            query="",
            predicates=[
                {"field": "product_type", "op": "eq", "value": "football"},
                {"field": "size", "op": "eq", "value": "43"},
                {"field": "available", "op": "eq", "value": True},
            ],
        )
        ids, advice, constraints, who = (
            ["shoe-12", "shoe-13"],
            ADVICE_SHOES,
            {"category": "shoes", "size": "43"},
            None,
        )
    elif message == TROUSERS_32:
        search = SearchQuery(
            query="", predicates=[{"field": "product_type", "op": "eq", "value": "trousers"}]
        )
        ids, advice, constraints, who = (
            ["clothing-08", "clothing-09"],
            ADVICE_TROUSERS,
            {"category": "clothing", "size": "32"},
            "brother",
        )
    else:
        raise ValueError("Unknown scripted decision request")
    if not evidence:
        return {"kind": "search", "query": search.model_dump(), "beneficiary": who}
    return {
        "kind": "recommend",
        "language": "ar",
        "selected_ids": ids,
        "constraints": constraints,
        "advice_message": advice,
        "beneficiary": who,
    }


class SizeModel:
    def __init__(self):
        self.requests = []

    async def complete(self, request):
        version = request.prompt_version
        if version.startswith("intent-"):
            context = json.loads(request.system.split("\n", 1)[0].split(": ", 1)[1])
            message = request.messages[-1].content
        else:
            context = json.loads(request.messages[0].content)
            message = context.get("message")
        self.requests.append({"prompt": version, "message": message})

        if version.startswith("catalogue-decision-"):
            response = decision(message, context["evidence"])
        elif version.startswith("advice-"):
            raise ValueError("Unexpected advice request")
        elif message == SHOES_43:
            response = intent("find_products", constraints={"size": "43"})
        elif message == TROUSERS_32:
            # On a product page the entry point is the action interpreter, which hands a
            # shopping search back to the catalogue decision loop.
            response = intent("find_products", constraints={"size": "32"}, beneficiary="brother")
        elif message == ADD_SHOE:
            # No size: the Shopper said it in an earlier message.
            response = add_intent(context, message, {"color": "blue"}, None)
        elif message == ADD_FOR_BROTHER:
            response = add_intent(context, message, {"color": "black"}, "brother")
        elif message == ADD_FOR_ME:
            # Wrong on purpose: "32" is the brother's size and nobody said it for "me".
            response = add_intent(context, message, {"size": "32", "color": "khaki"}, "me")
        else:
            raise ValueError("Unknown scripted size request")
        yield LLMChunk(text=json.dumps(response, ensure_ascii=False))


def build():
    model = SizeModel()
    sink = MemorySink()
    application = create_app(
        llm_settings=LLMSettings(provider="groq", model="offline-fixture"),
        llm_client=model,
        catalogue_retrieval_enabled=True,
        event_sink=sink,
    )

    @application.get("/__eval/size-requests")
    def size_requests():
        return model.requests

    @application.get("/__eval/event-records")
    def event_records():
        return sink.records

    return application


app = build()
