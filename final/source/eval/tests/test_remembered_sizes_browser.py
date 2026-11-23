"""Ticket 03 browser case: a size said once is remembered per person and size kind.

The model is scripted (no network); see eval/size_fixture_app.py. The scripted replies for the
adds carry no size, so a size on the page can only come from the Agent's Session memory.
"""

import json

from playwright.sync_api import expect, sync_playwright

from eval.browser_http import browser_post
from eval.services import local_services
from eval.size_fixture_app import (
    ADD_FOR_BROTHER,
    ADD_FOR_ME,
    ADD_SHOE,
    ADVICE_SHOES,
    ADVICE_TROUSERS,
    MESSAGES,
    SHOES_43,
    TROUSERS_32,
)

USED_NOTE_43 = "ضفتها بمقاس 43 زي ما قلت"
USED_NOTE_32 = "ضفتها بمقاس 32 زي ما قلت"


def send(page, message):
    page.locator("#shopper-message").fill(message)
    page.get_by_role("button", name="إرسال", exact=True).click()


def open_product(page, frame, product_id):
    frame.locator("body").evaluate(f"() => {{ location.href = '/p/{product_id}'; }}")
    expect(frame.locator("#product-size")).to_be_visible()
    expect(frame.locator("#product-size")).to_have_value("")


def cart_lines(page):
    lines = page.request.get("http://localhost:4000/cart/state").json()["lines"]
    return [(line["product_id"], line["quantity"], line["size"], line["color"]) for line in lines]


def suggestion_card(page, product_id):
    card = page.locator(f'[data-product-id="{product_id}"]')
    expect(card).to_be_visible(timeout=15000)
    return card


def test_remembered_size_is_used_per_person_and_never_invented():
    with local_services(agent_app="eval.size_fixture_app:app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            browser_post(page, "http://localhost:4000/__test/reset")
            page.goto("http://localhost:4100")
            expect(page.locator("#shopper-message")).to_be_enabled()
            frame = page.frame_locator("#storefront-frame")

            # 1. The owner's phrase: suggestions of football shoes (catalogue category shoes).
            send(page, SHOES_43)
            expect(page.get_by_text(ADVICE_SHOES, exact=True)).to_be_visible(timeout=15000)
            for product_id in ("shoe-12", "shoe-13"):
                suggestion_card(page, product_id)
            expect(page.locator("#shopper-message")).to_be_enabled()

            # 2. Open a shoe that offers 43; "add it, blue" names no size and is not asked.
            open_product(page, frame, "shoe-12")
            expect(frame.locator("#product-size")).to_be_visible()
            send(page, ADD_SHOE)
            expect(page.get_by_text(USED_NOTE_43)).to_be_visible(timeout=15000)
            expect(frame.locator("#product-size")).to_have_value("43")
            expect(page.locator("#pending-question")).to_be_hidden()
            assert cart_lines(page) == [("shoe-12", 1, "43", "blue")]
            expect(page.locator("#shopper-message")).to_be_enabled()

            # 3. A brother's trousers: his size is said once, then used on his page.
            send(page, TROUSERS_32)
            expect(page.get_by_text(ADVICE_TROUSERS, exact=True)).to_be_visible(timeout=15000)
            for product_id in ("clothing-08", "clothing-09"):
                suggestion_card(page, product_id)
            expect(page.locator("#shopper-message")).to_be_enabled()
            open_product(page, frame, "clothing-08")
            send(page, ADD_FOR_BROTHER)
            expect(page.get_by_text(USED_NOTE_32)).to_be_visible(timeout=15000)
            expect(frame.locator("#product-size")).to_have_value("32")
            assert cart_lines(page) == [
                ("shoe-12", 1, "43", "blue"),
                ("clothing-08", 1, "32", "black"),
            ]
            expect(page.locator("#shopper-message")).to_be_enabled()

            # 4. "For me" with an invented size: nothing is added, the size is asked.
            send(page, ADD_FOR_ME)
            question = page.locator("#pending-question")
            expect(question).to_be_visible(timeout=15000)
            expect(question).to_contain_text("المتاح: 30, 32, 34")
            expect(page.get_by_text("ضفتها بمقاس")).to_have_count(2)
            assert cart_lines(page) == [
                ("shoe-12", 1, "43", "blue"),
                ("clothing-08", 1, "32", "black"),
            ]

            # The scripted replies carried no size for the first two adds: the page size
            # control reached 43 and 32 through the Agent's remembered sizes alone.
            requests = page.request.get("http://localhost:8000/__eval/size-requests").json()
            assert [r["message"] for r in requests if r["prompt"].startswith("intent-")] == [
                ADD_SHOE,
                TROUSERS_32,
                ADD_FOR_BROTHER,
                ADD_FOR_ME,
            ]

            # The Agent's normal event records hold no size, person word or message text.
            records = page.request.get("http://localhost:8000/__eval/event-records").json()
            assert records
            for record in records:
                for value in record.values():
                    # Numbers (durations, counts) may coincide; no text value is a size or person.
                    if isinstance(value, str):
                        assert value not in {"43", "32", "30", "34", "brother", "me"}, record
            blob = json.dumps(records, ensure_ascii=False)
            assert "brother" not in blob and "أخو" not in blob
            for message in MESSAGES:
                assert message not in blob
        finally:
            browser.close()
