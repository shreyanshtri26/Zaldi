"""Built-in demo storefront with a real multi-step checkout (address -> delivery -> review -> payment).

It stands in for "the target storefront" so the browser automation can be developed and tested end to end.
Point ``STOREFRONT_URL`` at a real shop (and adapt ``automation.py``'s selectors) to drive that instead.
The /payment step is intentionally a stub: this app never handles card or UPI details.
"""
import re

from flask import Blueprint, redirect, render_template_string, request, url_for
from markupsafe import escape

from zaldi.checkout.tokens import sign, unsign
from zaldi.errors import ValidationError
from zaldi.services import cart

bp = Blueprint("store_sim", __name__, url_prefix="/store-sim")
EXPRESS_FEE = 149
FIELDS = (("full_name", "Full name"), ("phone", "Mobile number"), ("line1", "Address"), ("city", "City"),
          ("state", "State"), ("pincode", "PIN code"))
PAGE = """<!doctype html><meta charset="utf-8"><title>Zaldi demo store - checkout</title>
<style>body{font:15px system-ui;max-width:560px;margin:32px auto;padding:0 16px}label{display:block;margin:10px 0 2px}
input{width:100%;padding:8px}button{margin-top:16px;padding:10px 18px}.error{color:#b00020}table{width:100%}td:last-child{text-align:right}</style>
<h1>{{ title }}</h1>{% for e in errors %}<p class="error" role="alert">{{ e }}</p>{% endfor %}{{ body|safe }}"""


def _page(title: str, body: str, errors: list[str] | None = None, status: int = 200):
    return render_template_string(PAGE, title=title, body=body, errors=errors or []), status


def validate_address(form: dict) -> list[str]:
    errors = [f"{label} is required" for key, label in FIELDS if not (form.get(key) or "").strip()]
    if form.get("phone") and not re.fullmatch(r"[6-9]\d{9}", form["phone"].strip()):
        errors.append("Mobile number must be 10 digits starting with 6-9")
    if form.get("pincode") and not re.fullmatch(r"[1-9]\d{5}", form["pincode"].strip()):
        errors.append("PIN code must be 6 digits")
    return errors


def totals(session_id: str, method: str) -> dict:
    c = cart.get_cart(session_id)
    shipping = EXPRESS_FEE if method == "express" else c["shipping"]
    return {"subtotal": c["subtotal"], "discount": c["discount"], "shipping": shipping,
            "total": c["subtotal"] - c["discount"] + shipping, "item_count": c["item_count"]}


def _state(token: str) -> dict:
    try:
        return unsign("store-sim", token, max_age=900)
    except ValidationError:
        return {}


@bp.route("/checkout/address", methods=["GET", "POST"])
def address():
    token = request.args.get("cart", "")
    state = _state(token)
    if not state.get("session_id") or not cart.get_cart(state["session_id"])["items"]:
        return _page("Checkout", "<p>Your cart is empty or this link has expired.</p>", status=410)
    errors, form = [], dict(request.form)
    if request.method == "POST":
        errors = validate_address(form)
        if not errors:
            state["address"] = {k: form[k].strip() for k, _ in FIELDS}
            return redirect(url_for("store_sim.delivery", s=sign("store-sim", state)))
    inputs = "".join(f'<label for="{k}">{label}</label><input id="{k}" name="{k}" value="{escape(form.get(k, ""))}">'
                     for k, label in FIELDS)
    return _page("1. Delivery address", f'<form method="post">{inputs}<button type="submit">Continue</button></form>', errors)


@bp.route("/checkout/delivery", methods=["GET", "POST"])
def delivery():
    token = request.args.get("s", "")
    state = _state(token)
    if not state.get("address"):
        return _page("Checkout", "<p>This step has expired. Start again.</p>", status=410)
    if request.method == "POST":
        state["method"] = "express" if request.form.get("method") == "express" else "standard"
        return redirect(url_for("store_sim.review", s=sign("store-sim", state)))
    body = ('<form method="post"><label><input type="radio" name="method" value="standard" checked style="width:auto"> '
            'Standard (4-7 days)</label><label><input type="radio" name="method" value="express" style="width:auto"> '
            f'Express (1-2 days in metros) Rs. {EXPRESS_FEE}</label><button type="submit">Continue</button></form>')
    return _page("2. Delivery method", body)


@bp.get("/checkout/review")
def review():
    state = _state(request.args.get("s", ""))
    if not state.get("method"):
        return _page("Checkout", "<p>This step has expired. Start again.</p>", status=410)
    c, t = cart.get_cart(state["session_id"]), totals(state["session_id"], state["method"])
    rows = "".join(f"<tr><td>{i['quantity']} x {escape(i['product_name'])}</td><td>Rs. {i['line_total']:,}</td></tr>" for i in c["items"])
    a = state["address"]
    body = (f'<table>{rows}</table><p>Subtotal: <b id="subtotal">{t["subtotal"]}</b> | Discount: <b id="discount">{t["discount"]}</b>'
            f' | Shipping: <b id="shipping">{t["shipping"]}</b></p><h2>Total: Rs. <span id="order-total">{t["total"]}</span></h2>'
            f'<p id="ship-to">Ship to {escape(a["full_name"])}, {escape(a["line1"])}, {escape(a["city"])} - {escape(a["pincode"])}</p>'
            f'<p id="method">{state["method"]}</p>'
            f'<a href="{url_for("store_sim.payment", s=request.args["s"])}" id="proceed-to-payment"><button>Proceed to payment</button></a>')
    return _page("3. Review your order", body)


@bp.get("/checkout/payment")
def payment():
    return _page("4. Payment", "<p>Payment is completed by the customer on the payment gateway. "
                               "This demo store does not take payment.</p>")
