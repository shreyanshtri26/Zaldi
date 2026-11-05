"""Shopper endpoints (identified by the anonymous ``X-Session-Id`` header): cart, preferences and the checkout handshake."""
import re

from flask import Blueprint, jsonify, request

from zaldi.checkout import handshake
from zaldi.errors import ValidationError
from zaldi.services import cart, preferences

bp = Blueprint("shop", __name__)
SESSION_RE = re.compile(r"[A-Za-z0-9_-]{8,64}")


def session_id() -> str:
    sid = request.headers.get("X-Session-Id", "")
    if not SESSION_RE.fullmatch(sid):
        raise ValidationError("a valid X-Session-Id header is required")
    return sid


def _json() -> dict:
    return request.get_json(silent=True) or {}


def _int(value, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a whole number") from None


@bp.get("/cart")
def get_cart():
    return jsonify(cart.get_cart(session_id()))


@bp.post("/cart/items")
def add_item():
    data = _json()
    return jsonify(cart.add_item(session_id(), _int(data.get("product_id"), "product_id"), _int(data.get("quantity", 1), "quantity")))


@bp.put("/cart/items/<int:product_id>")
def set_quantity(product_id: int):
    return jsonify(cart.set_quantity(session_id(), product_id, _int(_json().get("quantity"), "quantity")))


@bp.delete("/cart/items/<int:product_id>")
def remove_item(product_id: int):
    return jsonify(cart.remove_item(session_id(), product_id))


@bp.post("/cart/coupon")
def coupon():
    return jsonify(cart.apply_coupon(session_id(), str(_json().get("code", ""))))


@bp.get("/preferences")
def get_preferences():
    return jsonify(preferences.get_preferences(session_id()))


@bp.put("/preferences")
def put_preferences():
    return jsonify(preferences.save_preferences(session_id(), _json()))


@bp.post("/checkout/prepare")
def prepare():
    """Run the browser automation up to the review step. Returns a summary and a token; nothing is ordered yet."""
    data = _json()
    return jsonify(handshake.prepare(session_id(), data.get("address") or {}, data.get("method", "standard"), request.host_url))


@bp.post("/checkout/confirm")
def confirm():
    return jsonify(handshake.confirm(session_id(), str(_json().get("token", ""))))


@bp.post("/checkout/cancel")
def cancel():
    return jsonify(handshake.cancel(session_id(), str(_json().get("token", ""))))
