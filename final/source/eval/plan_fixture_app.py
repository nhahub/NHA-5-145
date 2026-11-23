"""Scripted multi-step plan browser fixture ONLY. It tests execution, not language accuracy.

The scripted model answers by exact message text. Every model request is recorded (prompt
version, message, plan-step marker) and served at `/__eval/plan-requests` for the browser
cases to assert on.
"""

import json

from agent.app import create_app
from agent.catalogue_contract import SearchQuery
from agent.llm import LLMChunk, LLMSettings

ADD_THEN_CART = "ضيفلي الجزمة ديه للعربية مقاس 42 بعدها افتح العربية"
ADD_STEP = "ضيفلي الجزمة ديه للعربية مقاس 42"
CART_STEP = "افتح العربية"
ADD_THEN_PANTS = "ضيفلي ده وكمان عايز بنطلون لاخويا"
ADD_STEP_2 = "ضيفلي ده"
PANTS_STEP = "عايز بنطلون لاخويا"
ADVICE = "ده الأنسب لأخوك من الكتالوج."
# Step 2 asks for 99 more of a product already in the cart: the Storefront refuses it (the
# line would pass 99), so the plan fails there and step 3 never runs.
ADD_THEN_TOO_MANY_THEN_CART = (
    "ضيفلي الجزمة ديه للعربية مقاس 42 وبعدين ضيف 99 منها وبعدين افتح العربية"
)
TOO_MANY_STEP = "ضيف 99 منها"
# Ticket 07: a guarded step (clear the cart) at the end and in the middle of a sequence.
ADD_NO_SIZE = "ضيفلي الجزمة ديه للعربية"
CLEAR_STEP = "امسح العربية"
ACCOUNT_STEP = "افتح الحساب"
ADD_THEN_CLEAR = f"{ADD_NO_SIZE} بعدها {CLEAR_STEP}"
OPEN_CLEAR_ACCOUNT = f"{CART_STEP} وبعدين {CLEAR_STEP} وبعدين {ACCOUNT_STEP}"
# Ticket 08: two suggestion cards, then "this" with nothing to say which one is meant.
FIND_TWO = "دورلي على جزمتين"
ADD_THIS = "ضيفلي ديه للسلة"
# Ticket 09: "add it if it is under N" on the open product (shoe-01 costs 1450 EGP).
ADD_IF_UNDER_1000 = "ضيفها لو أقل من 1000"
ADD_IF_UNDER_2000 = "ضيفها لو أقل من 2000"


# Ticket 10: a colour swap (an add, then a removal), and one to a colour the product lacks.
SWAP_TO_YELLOW = "غيرت رأيي خليها صفرا بدل الأزرق"
SWAP_SOURCE = "خليها صفرا"
SWAP_TO_RED = "غيرت رأيي خليها احمر بدل الأزرق"
SWAP_RED_SOURCE = "خليها احمر"
# Copilot reliability 08: the model picks a product the message does not name.
OPEN_UNNAMED = "افتح الجزمة الجديدة"
UNNAMED_PRODUCT = "shoe-02"
# Copilot reliability 06: a product named in a fresh session; the name is exactly one product's.
OPEN_BY_NAME = "افتح خطوة سريعة"
NAMED_PRODUCT_NAME = "خطوة سريعة"


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


def add_intent(context, source, quantity=1, **steps):
    control = next(
        e
        for e in context["current_snapshot"]["elements"]
        if e.get("form_action") == "/cart/items" and e["role"] == "button"
    )
    return intent(
        "cart_edit",
        cart_operation="add",
        cart_target_id=control["id"],
        cart_quantity=quantity,
        cart_quantity_mode="set",
        cart_source=source,
        **steps,
    )


class PlanModel:
    def __init__(self):
        self.requests = []

    async def complete(self, request):
        version = request.prompt_version
        if version.startswith("intent-"):
            context = json.loads(request.system.split("\n", 1)[0].split(": ", 1)[1])
            message = request.messages[-1].content
            marker = context.get("resolved_state", {}).get("_plan_step")
        else:
            context = json.loads(request.messages[0].content)
            message = context.get("message")
            marker = context.get("plan_step")
        self.requests.append({"prompt": version, "message": message, "plan_step": marker})

        if version.startswith("advice-"):
            response = {
                "v": 1,
                "message": ADVICE,
                "product_ids": [p["id"] for p in context["products"]][:1],
            }
        elif version.startswith("catalogue-decision-"):
            if message == PANTS_STEP and not context["evidence"]:
                response = {
                    "kind": "search",
                    "query": SearchQuery(
                        query="",
                        requirements=[{"field": "feature", "op": "exclude", "value": "leather"}],
                    ).model_dump(),
                }
            elif message == PANTS_STEP:
                response = {
                    "kind": "recommend",
                    "language": "ar",
                    "selected_ids": ["shoe-09"],
                    "advice_message": ADVICE,
                }
            elif message == FIND_TWO and not context["evidence"]:
                response = {
                    "kind": "search",
                    "query": SearchQuery(
                        query="",
                        requirements=[{"field": "feature", "op": "exclude", "value": "leather"}],
                    ).model_dump(),
                }
            elif message == FIND_TWO:
                ids = [p["id"] for p in context["evidence"][-1]["advice_products"]][:2]
                response = {
                    "kind": "recommend",
                    "language": "ar",
                    "selected_ids": ids,
                    "advice_message": ADVICE,
                }
            elif message == OPEN_BY_NAME:
                response = {"kind": "execute"}
            else:
                raise ValueError("Unknown scripted decision request")
        elif message in {ADD_IF_UNDER_1000, ADD_IF_UNDER_2000}:
            # The model only names the fact, the comparator and the value; code reads the price.
            response = add_intent(
                context,
                "ضيفها",
                product_id="shoe-01",
                condition={
                    "fact": "price",
                    "comparator": "lt",
                    "value": "1000" if message == ADD_IF_UNDER_1000 else "2000",
                },
            )
        elif message in {SWAP_TO_YELLOW, SWAP_TO_RED}:
            # Only the operation, the NEW colour and the observed remove button of the line;
            # code reads the old line and does the add and the removal.
            control = next(
                e
                for e in context["current_snapshot"]["elements"]
                if e.get("form_action") == "/cart/remove" and e["role"] == "button"
            )
            yellow = message == SWAP_TO_YELLOW
            response = intent(
                "cart_edit",
                cart_operation="replace",
                cart_target_id=control["id"],
                cart_source=SWAP_SOURCE if yellow else SWAP_RED_SOURCE,
                constraints={"color": "yellow" if yellow else "red"},
            )
        elif message == OPEN_UNNAMED:
            # The model picks an id the words never name; code must ask before opening it.
            response = intent(
                "open_product", product_id=UNNAMED_PRODUCT, navigation_source=OPEN_UNNAMED
            )
        elif message == OPEN_BY_NAME:
            # Only the marker and the name the Shopper said; code finds the product.
            response = intent(
                "find_products",
                constraints={"query": NAMED_PRODUCT_NAME},
                request_mode="open",
            )
        elif message == ADD_THIS:
            # Only the marker: which product "this" means is decided by code, never here.
            response = intent(
                "cart_edit",
                cart_operation="add",
                cart_quantity=1,
                cart_quantity_mode="set",
                cart_source=ADD_THIS,
                refers_to_this=True,
            )
        elif message == ADD_THEN_CART:
            response = add_intent(
                context, ADD_STEP, first_step=ADD_STEP, remaining_steps=[CART_STEP]
            )
        elif message == ADD_THEN_TOO_MANY_THEN_CART:
            response = add_intent(
                context,
                ADD_STEP,
                first_step=ADD_STEP,
                remaining_steps=[TOO_MANY_STEP, CART_STEP],
            )
        elif message == ADD_THEN_CLEAR:
            response = add_intent(
                context, ADD_NO_SIZE, first_step=ADD_NO_SIZE, remaining_steps=[CLEAR_STEP]
            )
        elif message == CLEAR_STEP:
            response = intent("mutate", mutation_kind="clear_cart", mutation_source=CLEAR_STEP)
        elif message == OPEN_CLEAR_ACCOUNT:
            response = intent(
                "navigate",
                constraints={"target": "cart"},
                first_step=CART_STEP,
                remaining_steps=[CLEAR_STEP, ACCOUNT_STEP],
            )
        elif message == ACCOUNT_STEP:
            response = intent("navigate", constraints={"target": "account"})
        elif message == TOO_MANY_STEP:
            response = add_intent(context, TOO_MANY_STEP, quantity=99)
        elif message == CART_STEP:
            response = intent("navigate", constraints={"target": "cart"})
        elif message == PANTS_STEP:
            # On a product page the entry point is the action interpreter, which hands a
            # shopping search back to the catalogue decision loop.
            response = intent("find_products")
        elif message == ADD_THEN_PANTS:
            response = add_intent(
                context, ADD_STEP_2, first_step=ADD_STEP_2, remaining_steps=[PANTS_STEP]
            )
        else:
            raise ValueError("Unknown scripted plan request")
        yield LLMChunk(text=json.dumps(response, ensure_ascii=False))


def build(retrieval):
    model = PlanModel()
    application = create_app(
        llm_settings=LLMSettings(provider="groq", model="offline-fixture"),
        llm_client=model,
        catalogue_retrieval_enabled=retrieval,
    )

    @application.get("/__eval/plan-requests")
    def plan_requests():
        return model.requests

    return application


app = build(False)
retrieval_app = build(True)
