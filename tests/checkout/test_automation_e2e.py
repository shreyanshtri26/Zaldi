"""Real headless-browser run of the checkout automation against the built-in demo storefront (served on a local port).

Skipped when Playwright or a browser is unavailable. Set BROWSER_CHANNEL=msedge|chrome to use an installed browser.
"""
import os
import threading

import pytest

from zaldi import config, create_app
from zaldi.checkout import automation, handshake
from zaldi.checkout.tokens import sign
from zaldi.db import content_repo
from zaldi.services import cart

playwright = pytest.importorskip("playwright.sync_api")
SID = "sess-e2e-0001"
ADDRESS = {"full_name": "Riya Sharma", "phone": "9876543210", "line1": "12, MG Road", "city": "Bengaluru",
           "state": "Karnataka", "pincode": "560001"}


@pytest.fixture
def server(temp_db, monkeypatch):
    from werkzeug.serving import make_server

    monkeypatch.setattr(config, "BROWSER_CHANNEL", os.getenv("BROWSER_CHANNEL", "msedge"))
    app = create_app()
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture
def browser_ok(server):
    try:
        with playwright.sync_playwright() as p:
            p.chromium.launch(headless=True, channel=config.BROWSER_CHANNEL or None).close()
    except Exception as exc:
        pytest.skip(f"no usable browser: {exc}")


def saree():
    return next(p for p in content_repo.list_rows("products") if "Banarasi" in p["product_name"])


def token():
    return sign("store-sim", {"session_id": SID})


def test_automation_fills_checkout_and_stops_at_review(server, browser_ok):
    cart.add_item(SID, saree()["id"], 2)
    seen = automation.run_checkout(server, token(), ADDRESS, "standard")
    expected = cart.get_cart(SID)
    assert seen["totals"]["subtotal"] == expected["subtotal"] == saree()["price"] * 2
    assert seen["totals"]["total"] == expected["total"]
    assert "Riya Sharma" in seen["ship_to"] and "560001" in seen["ship_to"]


def test_express_shipping_changes_total(server, browser_ok):
    cart.add_item(SID, saree()["id"])
    std = automation.run_checkout(server, token(), ADDRESS, "standard")["totals"]
    exp = automation.run_checkout(server, token(), ADDRESS, "express")["totals"]
    assert exp["shipping"] == 149 and exp["total"] == std["total"] - std["shipping"] + 149


def test_coupon_flows_through_to_the_storefront(server, browser_ok):
    cart.add_item(SID, saree()["id"])
    cart.apply_coupon(SID, "WELCOME10")
    assert automation.run_checkout(server, token(), ADDRESS)["totals"]["discount"] == cart.get_cart(SID)["discount"] > 0


def test_storefront_validation_errors_are_reported(server, browser_ok):
    cart.add_item(SID, saree()["id"])
    with pytest.raises(automation.CheckoutError, match="Mobile number"):
        automation.run_checkout(server, token(), ADDRESS | {"phone": "123"})


def test_expired_or_forged_cart_link_fails_cleanly(server, browser_ok):
    cart.add_item(SID, saree()["id"])
    with pytest.raises(automation.CheckoutError, match="unavailable"):
        automation.run_checkout(server, token() + "tampered", ADDRESS)


def test_payment_step_is_unreachable_for_the_automation(server, browser_ok):
    """Defence in depth: even if a bug clicked through, the browser route to /payment is aborted."""
    cart.add_item(SID, saree()["id"])
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel=config.BROWSER_CHANNEL or None)
        page = browser.new_page()
        import re

        page.route(re.compile(r".*/checkout/payment.*"), lambda r: r.abort())
        with pytest.raises(playwright.Error):
            page.goto(f"{server}/store-sim/checkout/payment?s=x")
        browser.close()


def test_full_handshake_through_real_browser(server, browser_ok):
    cart.add_item(SID, saree()["id"])
    stock = saree()["stock_quantity"]
    prepared = handshake.prepare(SID, ADDRESS, "standard", server)
    assert prepared["status"] == "awaiting_confirmation" and saree()["stock_quantity"] == stock
    done = handshake.confirm(SID, prepared["token"])
    assert done["status"] == "confirmed" and saree()["stock_quantity"] == stock - 1
