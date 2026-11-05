import pytest

from zaldi.checkout import automation, store_sim
from zaldi.db import content_repo

H = {"X-Session-Id": "sess-api-0001"}
ADDRESS = {"full_name": "Riya Sharma", "phone": "9876543210", "line1": "12, MG Road", "city": "Bengaluru",
           "state": "Karnataka", "pincode": "560001"}


def product(client, name="Banarasi"):
    return next(p for p in client.get("/api/products").get_json() if name in p["product_name"])


def fake_runner(session_totals=None):
    """Stand-in for the browser: reports the totals the simulator would show (or tampered ones)."""
    def run(base_url, cart_token, address, method):
        from zaldi.checkout.tokens import unsign

        sid = unsign("store-sim", cart_token, 900)["session_id"]
        return {"totals": session_totals or store_sim.totals(sid, method), "ship_to": "x", "method": method}
    return run


@pytest.fixture
def cart_with_saree(client):
    client.post("/api/cart/items", json={"product_id": product(client)["id"], "quantity": 2}, headers=H)
    return client


def test_session_header_required_and_validated(client):
    assert client.get("/api/cart").status_code == 400
    assert client.get("/api/cart", headers={"X-Session-Id": "short"}).status_code == 400
    assert client.get("/api/cart", headers={"X-Session-Id": "../../etc/passwd"}).status_code == 400
    assert client.get("/api/cart", headers=H).get_json()["items"] == []


def test_cart_crud_over_http(client):
    p = product(client)
    r = client.post("/api/cart/items", json={"product_id": p["id"]}, headers=H)
    assert r.status_code == 200 and r.get_json()["item_count"] == 1
    assert client.put(f"/api/cart/items/{p['id']}", json={"quantity": 3}, headers=H).get_json()["item_count"] == 3
    assert client.post("/api/cart/coupon", json={"code": "WELCOME10"}, headers=H).get_json()["discount"] > 0
    assert client.post("/api/cart/coupon", json={"code": "NOPE1"}, headers=H).status_code == 400
    assert client.delete(f"/api/cart/items/{p['id']}", headers=H).get_json()["items"] == []


@pytest.mark.parametrize("body", [{}, {"product_id": "abc"}, {"product_id": 99999}, {"product_id": 1, "quantity": 0},
                                  {"product_id": 1, "quantity": "x"}, {"product_id": 1, "quantity": 999}])
def test_cart_rejects_bad_input(client, body):
    assert client.post("/api/cart/items", json=body, headers=H).status_code == 400


def test_carts_are_isolated_per_session(client):
    client.post("/api/cart/items", json={"product_id": product(client)["id"]}, headers=H)
    assert client.get("/api/cart", headers={"X-Session-Id": "another-session-1"}).get_json()["items"] == []


def test_preferences_roundtrip_and_validation(client):
    r = client.put("/api/preferences", json={"max_price": "1500", "gender": "Women", "exclude_brands": "Biba Style"}, headers=H)
    assert r.get_json()["max_price"] == 1500
    assert client.get("/api/preferences", headers=H).get_json()["exclude_brands"] == "Biba Style"
    assert client.put("/api/preferences", json={"max_price": -5}, headers=H).status_code == 400
    assert client.put("/api/preferences", json={"gender": "x"}, headers=H).status_code == 400


def test_chat_requires_session_and_message(client):
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 400
    assert client.post("/api/chat", json={"message": "  "}, headers=H).status_code == 400


def test_chat_rejects_bad_image(client):
    from io import BytesIO

    r = client.post("/api/chat", data={"message": "this", "image": (BytesIO(b"%PDF"), "a.pdf", "application/pdf")},
                    headers=H, content_type="multipart/form-data")
    assert r.status_code == 400 and "JPEG" in r.get_json()["error"]


# ---- checkout handshake ----------------------------------------------------------------------------------
def test_prepare_halts_and_nothing_is_ordered(cart_with_saree, monkeypatch):
    monkeypatch.setattr(automation, "run_checkout", fake_runner())
    stock = product(cart_with_saree)["stock_quantity"]
    r = cart_with_saree.post("/api/checkout/prepare", json={"address": ADDRESS}, headers=H)
    body = r.get_json()
    assert r.status_code == 200 and body["status"] == "awaiting_confirmation" and body["token"]
    assert body["ship_to"]["phone"].endswith("3210") and "9876" not in body["ship_to"]["phone"]
    assert product(cart_with_saree)["stock_quantity"] == stock  # untouched
    assert cart_with_saree.get("/api/cart", headers=H).get_json()["item_count"] == 2  # cart intact


def test_confirm_places_order_once(cart_with_saree, monkeypatch):
    monkeypatch.setattr(automation, "run_checkout", fake_runner())
    stock = product(cart_with_saree)["stock_quantity"]
    token = cart_with_saree.post("/api/checkout/prepare", json={"address": ADDRESS}, headers=H).get_json()["token"]
    r = cart_with_saree.post("/api/checkout/confirm", json={"token": token}, headers=H)
    assert r.status_code == 200 and r.get_json()["status"] == "confirmed"
    assert product(cart_with_saree)["stock_quantity"] == stock - 2
    assert cart_with_saree.get("/api/cart", headers=H).get_json()["items"] == []
    again = cart_with_saree.post("/api/checkout/confirm", json={"token": token}, headers=H)
    assert again.status_code == 400 and "already" in again.get_json()["error"]
    assert product(cart_with_saree)["stock_quantity"] == stock - 2  # no double decrement


def test_confirm_needs_matching_session_and_valid_token(cart_with_saree, monkeypatch):
    monkeypatch.setattr(automation, "run_checkout", fake_runner())
    token = cart_with_saree.post("/api/checkout/prepare", json={"address": ADDRESS}, headers=H).get_json()["token"]
    other = {"X-Session-Id": "someone-else-1"}
    assert cart_with_saree.post("/api/checkout/confirm", json={"token": token}, headers=other).status_code == 400
    assert cart_with_saree.post("/api/checkout/confirm", json={"token": token + "x"}, headers=H).status_code == 400
    assert cart_with_saree.post("/api/checkout/confirm", json={}, headers=H).status_code == 400


def test_expired_token_rejected(cart_with_saree, monkeypatch):
    from zaldi import config

    monkeypatch.setattr(automation, "run_checkout", fake_runner())
    token = cart_with_saree.post("/api/checkout/prepare", json={"address": ADDRESS}, headers=H).get_json()["token"]
    monkeypatch.setattr(config, "HANDSHAKE_TTL", -1)
    assert "expired" in cart_with_saree.post("/api/checkout/confirm", json={"token": token}, headers=H).get_json()["error"]


def test_price_change_after_review_blocks_confirmation(cart_with_saree, monkeypatch):
    monkeypatch.setattr(automation, "run_checkout", fake_runner())
    token = cart_with_saree.post("/api/checkout/prepare", json={"address": ADDRESS}, headers=H).get_json()["token"]
    content_repo.update_row("products", product(cart_with_saree)["id"], {"price": 1})
    r = cart_with_saree.post("/api/checkout/confirm", json={"token": token}, headers=H)
    assert r.status_code == 400 and "changed" in r.get_json()["error"]


def test_stock_sold_out_between_review_and_confirm(cart_with_saree, monkeypatch):
    monkeypatch.setattr(automation, "run_checkout", fake_runner())
    token = cart_with_saree.post("/api/checkout/prepare", json={"address": ADDRESS}, headers=H).get_json()["token"]
    content_repo.update_row("products", product(cart_with_saree)["id"], {"stock_quantity": 1})
    r = cart_with_saree.post("/api/checkout/confirm", json={"token": token}, headers=H)
    assert r.status_code == 400 and "out of stock" in r.get_json()["error"]
    assert product(cart_with_saree)["stock_quantity"] == 1  # nothing partially applied


def test_storefront_total_mismatch_refused(cart_with_saree, monkeypatch):
    bad = {"subtotal": 1, "discount": 0, "shipping": 0, "total": 1}
    monkeypatch.setattr(automation, "run_checkout", fake_runner(bad))
    r = cart_with_saree.post("/api/checkout/prepare", json={"address": ADDRESS}, headers=H)
    assert r.status_code == 400 and "do not match" in r.get_json()["error"]


def test_new_prepare_cancels_previous_pending(cart_with_saree, monkeypatch):
    monkeypatch.setattr(automation, "run_checkout", fake_runner())
    old = cart_with_saree.post("/api/checkout/prepare", json={"address": ADDRESS}, headers=H).get_json()["token"]
    cart_with_saree.post("/api/checkout/prepare", json={"address": ADDRESS}, headers=H)
    assert "cancelled" in cart_with_saree.post("/api/checkout/confirm", json={"token": old}, headers=H).get_json()["error"]


def test_cancel(cart_with_saree, monkeypatch):
    monkeypatch.setattr(automation, "run_checkout", fake_runner())
    token = cart_with_saree.post("/api/checkout/prepare", json={"address": ADDRESS}, headers=H).get_json()["token"]
    assert cart_with_saree.post("/api/checkout/cancel", json={"token": token}, headers=H).get_json()["status"] == "cancelled"
    assert cart_with_saree.post("/api/checkout/confirm", json={"token": token}, headers=H).status_code == 400


@pytest.mark.parametrize("patch, fragment", [
    ({"phone": "12345"}, "Mobile number"), ({"pincode": "12"}, "PIN code"), ({"city": ""}, "City is required"),
])
def test_bad_address_rejected_before_browser_starts(cart_with_saree, monkeypatch, patch, fragment):
    monkeypatch.setattr(automation, "run_checkout", lambda *a: (_ for _ in ()).throw(AssertionError("browser started")))
    r = cart_with_saree.post("/api/checkout/prepare", json={"address": ADDRESS | patch}, headers=H)
    assert r.status_code == 400 and fragment in r.get_json()["error"]


def test_empty_cart_cannot_checkout(client):
    assert "empty" in client.post("/api/checkout/prepare", json={"address": ADDRESS}, headers=H).get_json()["error"]
