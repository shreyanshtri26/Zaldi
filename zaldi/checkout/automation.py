"""Headless-browser checkout automation (Playwright).

Drives the storefront's multi-step checkout (address -> delivery -> review) exactly like a customer would, then STOPS on
the review page. It never opens the payment step: the route is blocked in the browser as a second safeguard, and a
human must confirm through the handshake (see ``handshake.py``).
"""
import re

from zaldi import config
from zaldi.checkout.store_sim import FIELDS
from zaldi.errors import ValidationError

TIMEOUT_MS = 15000


class CheckoutError(ValidationError):
    """The storefront rejected something (field validation, expired cart) or changed shape."""


def _int(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text) or 0)


def run_checkout(base_url: str, cart_token: str, address: dict, method: str = "standard") -> dict:
    """Fill the checkout and return what the review page shows: ``{"totals": {...}, "ship_to": str, "method": str}``."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    base = (config.STOREFRONT_URL or base_url).rstrip("/")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel=config.BROWSER_CHANNEL or None,
                                        args=["--no-sandbox"] if config.BROWSER_NO_SANDBOX else [])
            try:
                page = browser.new_page()
                page.set_default_timeout(TIMEOUT_MS)
                page.route(re.compile(r".*/checkout/payment.*"), lambda route: route.abort())  # never reach payment

                page.goto(f"{base}/store-sim/checkout/address?cart={cart_token}")
                if "Delivery address" not in page.title() and not page.locator("input[name=full_name]").count():
                    raise CheckoutError("the checkout page is unavailable (your cart may have expired)")
                for key, _ in FIELDS:
                    page.fill(f"input[name={key}]", str(address.get(key, "")))
                page.click("button[type=submit]")
                page.wait_for_load_state()
                if errors := page.locator(".error").all_inner_texts():
                    raise CheckoutError("; ".join(errors))

                page.check(f"input[name=method][value={'express' if method == 'express' else 'standard'}]")
                page.click("button[type=submit]")
                page.wait_for_selector("#order-total")
                if "/checkout/review" not in page.url:
                    raise CheckoutError("checkout did not reach the review step")

                return {
                    "totals": {k: _int(page.inner_text(f"#{k}")) for k in ("subtotal", "discount", "shipping")}
                              | {"total": _int(page.inner_text("#order-total"))},
                    "ship_to": page.inner_text("#ship-to"),
                    "method": page.inner_text("#method").strip(),
                }
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise CheckoutError(f"browser automation failed: {str(exc).splitlines()[0]}") from exc
