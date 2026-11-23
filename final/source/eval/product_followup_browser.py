"""Opt-in live two-turn browser check for a named recommended product."""

import time

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto("http://localhost:4100/")
            page.locator("#shopper-message").fill("رشحلي كوتشي كاجوال بيج مقاس 43")
            page.get_by_role("button", name="إرسال").click()
            expect(page.locator('[data-product-id="shoe-09"]')).to_be_visible(timeout=60_000)
            print("verified_recommendation=shoe-09", flush=True)
            time.sleep(45)
            page.locator("#shopper-message").fill("طب ينفع توريني صفحة كوتشي ممشى النيل ده")
            page.get_by_role("button", name="إرسال").click()
            frame = page.frame_locator("#storefront-frame")
            expect(frame.locator('article[data-product-id="shoe-09"] h1')).to_have_text(
                "ممشى النيل", timeout=60_000
            )
            print("opened_exact_product_page=shoe-09", flush=True)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
