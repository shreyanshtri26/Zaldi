"""Checkout handshake: the automation prepares the order and halts; only the customer's explicit confirmation completes it.

prepare()  runs the browser to the review page, cross-checks the storefront's totals against our cart, stores a pending
           order and returns a signed one-time token.
confirm()  needs that token (bound to the session, expiring, single use), re-checks stock and prices, then places the order.
Nothing here ever handles card or UPI details: payment happens on the gateway, outside this app.
"""
import json
import secrets

from zaldi import config
from zaldi.checkout import automation, store_sim
from zaldi.checkout.tokens import sign, unsign
from zaldi.db import connect
from zaldi.errors import ValidationError
from zaldi.services import cart

SALT = "handshake"


def mask_address(a: dict) -> dict:
    """What we echo back to the customer: the address they typed so they can verify it, with the phone number masked."""
    phone = a.get("phone", "")
    return {**{k: a.get(k) for k in ("full_name", "line1", "city", "state", "pincode")},
            "phone": "*" * max(0, len(phone) - 4) + phone[-4:]}


def _public(order_id: str, token: str, summary: dict) -> dict:
    return {"order_id": order_id, "token": token, "status": "awaiting_confirmation",
            "expires_in": config.HANDSHAKE_TTL, "items": summary["items"], "totals": summary["totals"],
            "method": summary["method"], "ship_to": mask_address(summary["address"]),
            "notice": "Nothing has been ordered or paid yet. Confirm to place the order."}


def prepare(session_id: str, address: dict, method: str, base_url: str, runner=None) -> dict:
    c = cart.get_cart(session_id)
    if not c["items"]:
        raise ValidationError("your cart is empty")
    if c["warnings"]:
        raise ValidationError("please fix your cart first: " + "; ".join(c["warnings"]))
    if errors := store_sim.validate_address(address):
        raise ValidationError("; ".join(errors))
    method = "express" if method == "express" else "standard"

    seen = (runner or automation.run_checkout)(base_url, sign("store-sim", {"session_id": session_id}), address, method)
    expected = store_sim.totals(session_id, method)
    if any(seen["totals"].get(k) != expected[k] for k in ("subtotal", "discount", "shipping", "total")):
        raise automation.CheckoutError("the store's totals do not match your cart, so nothing was prepared")

    summary = {"items": [{k: i[k] for k in ("id", "product_name", "quantity", "price", "line_total")} for i in c["items"]],
               "totals": seen["totals"], "method": method, "address": {k: address[k].strip() for k, _ in store_sim.FIELDS}}
    order_id = secrets.token_hex(6)
    with connect() as conn:
        conn.execute("UPDATE orders SET status='cancelled' WHERE session_id=? AND status='pending'", (session_id,))
        conn.execute("INSERT INTO orders (id, session_id, summary) VALUES (?,?,?)", (order_id, session_id, json.dumps(summary)))
    return _public(order_id, sign(SALT, {"order_id": order_id, "session_id": session_id}), summary)


def _load(session_id: str, token: str) -> tuple[str, dict]:
    payload = unsign(SALT, token, config.HANDSHAKE_TTL)
    if payload.get("session_id") != session_id:
        raise ValidationError("this confirmation belongs to another session")
    with connect() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (payload["order_id"],)).fetchone()
    if row is None:
        raise ValidationError("order not found")
    if row["status"] != "pending":
        raise ValidationError(f"this order is already {row['status']}")
    return row["id"], json.loads(row["summary"])


def confirm(session_id: str, token: str) -> dict:
    order_id, summary = _load(session_id, token)
    now = store_sim.totals(session_id, summary["method"])
    if now["total"] != summary["totals"]["total"]:
        raise ValidationError("prices or your cart changed since you reviewed this order; please check out again")
    with connect() as conn:
        for item in summary["items"]:
            ok = conn.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=? AND stock_quantity >= ?",
                              (item["quantity"], item["id"], item["quantity"])).rowcount
            if not ok:
                raise ValidationError(f"{item['product_name']} just went out of stock; nothing was ordered")
        placed = conn.execute("UPDATE orders SET status='confirmed', confirmed_at=CURRENT_TIMESTAMP "
                              "WHERE id=? AND status='pending'", (order_id,)).rowcount
        if not placed:
            raise ValidationError("this order was already handled")
        conn.execute("DELETE FROM cart_items WHERE session_id=?", (session_id,))
    return {"order_id": order_id, "status": "confirmed", "totals": summary["totals"],
            "message": "Order confirmed. No payment was taken: this demo store has no payment gateway connected."}


def cancel(session_id: str, token: str) -> dict:
    order_id, _ = _load(session_id, token)
    with connect() as conn:
        conn.execute("UPDATE orders SET status='cancelled' WHERE id=? AND status='pending'", (order_id,))
    return {"order_id": order_id, "status": "cancelled"}
