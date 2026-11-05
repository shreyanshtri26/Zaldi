"""Cart messages in chat ("add the second one", "remove the saree", "show my cart"). Deterministic: no LLM, no guessing."""
import re
from dataclasses import dataclass

from zaldi.errors import ValidationError
from zaldi.search.extract import extract_filters
from zaldi.search.hybrid import search
from zaldi.services import cart

ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "fifth": 5,
            "5th": 5, "sixth": 6, "6th": 6, "pehla": 1, "pehle": 1, "dusra": 2, "dusre": 2, "teesra": 3, "teesre": 3}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ek": 1, "do": 2, "teen": 3}
CLEAR_RE = re.compile(r"\b(clear|empty|reset)\b.*\b(cart|bag|basket)\b|\b(cart|bag)\b.*\b(clear|empty)\b", re.I)
SHOW_RE = re.compile(r"\b(show|view|see|what'?s|whats|what is|display|dikhao|check|total)\b.*\b(cart|bag|basket)\b|^\s*(my )?(cart|bag)\s*\??$", re.I)
REMOVE_RE = re.compile(r"\b(remove|delete|hata|hatao|nikal|drop|take out)\b", re.I)
SET_QTY_RE = re.compile(r"\b(?:change|set|update|make)\b.*?\b(?:quantity|qty)\b.*?\b(\d+)\b|\b(?:quantity|qty)\b.*?\b(?:to|=)\s*(\d+)\b", re.I)
COUPON_RE = re.compile(r"\b(?:coupon|promo|code|apply)\b\s*(?:code\s*)?[:\-]?\s*([A-Za-z]+\d+)\b", re.I)


@dataclass
class CartIntent:
    action: str  # add | remove | set_quantity | show | clear | coupon
    ordinal: int | None = None  # 1-based position in the last results; -1 = last
    quantity: int = 1
    coupon: str | None = None
    name_query: str = ""


def parse_intent(text: str) -> CartIntent:
    t = text.lower()
    if m := COUPON_RE.search(text):
        return CartIntent("coupon", coupon=m[1].upper())
    if CLEAR_RE.search(t):
        return CartIntent("clear")
    ordinal = next((n for w, n in ORDINALS.items() if re.search(rf"\b{w}\b", t)), None)
    if ordinal is None and "last" in t.split():
        ordinal = -1
    if ordinal is None and (m := re.search(r"(?:#|number|no\.?|item)\s*(\d)\b", t)):
        ordinal = int(m[1])
    if m := SET_QTY_RE.search(t):
        return CartIntent("set_quantity", ordinal, int(m[1] or m[2]))
    qty = 1
    if m := re.search(r"\b(\d{1,2})\s*(?:x|of|pieces?|pcs|units?|qty)\b|\bx\s*(\d{1,2})\b|\badd\s+(\d{1,2})\b", t):
        qty = int(next(g for g in m.groups() if g))
    elif m := re.search(r"\b(one|two|three|four|five|ek|do|teen)\s+(?:of|piece|pieces)\b", t):
        qty = NUMBER_WORDS[m[1]]
    if REMOVE_RE.search(t):
        return CartIntent("remove", ordinal, qty, name_query=_name_part(t))
    if SHOW_RE.search(t) and not re.search(r"\b(add|buy)\b", t):
        return CartIntent("show")
    return CartIntent("add", ordinal, qty, name_query=_name_part(t))


def _name_part(text: str) -> str:
    """What is left of the message once cart verbs and references are removed ("add the cotton kurta" -> "cotton kurta")."""
    junk = r"\b(add|put|remove|delete|hata|hatao|buy|take|i|want|to|my|the|a|an|this|that|it|one|ones|these|those|cart|bag|basket|" \
           r"from|in|into|please|daal|do|karo|first|second|third|fourth|fifth|last|\d+(st|nd|rd|th)?|x|of|pieces?|pcs|item|number|no)\b"
    return re.sub(r"\s+", " ", re.sub(junk, " ", re.sub(r"[^\w\s]", " ", text))).strip()


def _resolve(intent: CartIntent, pool_ids: list[int], allow_catalogue: bool) -> dict | None:
    """The product the customer means: by position, by name, or "it" (the first thing in view).

    ``pool_ids`` is what they can see (last search results, or the cart lines when removing).
    """
    from zaldi.db import content_repo

    pool = [p for p in (content_repo.get_row("products", pid) for pid in pool_ids) if p]
    if intent.ordinal:
        idx = len(pool) - 1 if intent.ordinal == -1 else intent.ordinal - 1
        return pool[idx] if 0 <= idx < len(pool) else None
    if intent.name_query:
        words = set(intent.name_query.split())
        hit = next((p for p in pool if words & set(p["product_name"].lower().split())), None)
        if hit or not allow_catalogue:
            return hit
        rows, _ = search(intent.name_query, extract_filters(intent.name_query), limit=1)
        return rows[0] if rows else None
    return pool[0] if pool else None


def _money(n: int) -> str:
    return f"Rs. {n:,}"


def describe_cart(c: dict) -> str:
    if not c["items"]:
        return "Your cart is empty."
    lines = [f"- {i['quantity']} x {i['product_name']} ({i['color']}) - {_money(i['line_total'])}" for i in c["items"]]
    lines.append(f"Subtotal {_money(c['subtotal'])}")
    if c["discount"]:
        lines.append(f"Coupon {c['coupon']}: -{_money(c['discount'])}")
    lines.append("Shipping: free" if not c["shipping"] else f"Shipping: {_money(c['shipping'])}")
    lines.append(f"Total {_money(c['total'])}")
    if c["free_shipping_gap"]:
        lines.append(f"Add {_money(c['free_shipping_gap'])} more for free shipping.")
    return "\n".join(lines + c["warnings"])


def handle_cart_message(session_id: str, text: str) -> dict:
    """Returns {"response", "cart"}; validation problems become a polite message instead of an error."""
    intent = parse_intent(text)
    try:
        if intent.action == "show":
            return {"response": describe_cart(cart.get_cart(session_id)), "cart": cart.get_cart(session_id)}
        if intent.action == "clear":
            return {"response": "Done, your cart is now empty.", "cart": cart.clear_cart(session_id)}
        if intent.action == "coupon":
            c = cart.apply_coupon(session_id, intent.coupon)
            return {"response": f"Coupon {c['coupon']} applied.\n{describe_cart(c)}", "cart": c}

        shown = cart.last_results(session_id)
        in_cart = [i["id"] for i in cart.get_cart(session_id)["items"]]
        editing = intent.action in ("remove", "set_quantity")
        product = _resolve(intent, in_cart if editing else shown, allow_catalogue=not editing)
        if product is None:
            hint = "Tell me which item (for example 'add the first one'), or search for something first."
            return {"response": f"I couldn't tell which product you mean. {hint}", "cart": cart.get_cart(session_id)}
        if intent.action == "remove":
            c = cart.remove_item(session_id, product["id"])
            return {"response": f"Removed {product['product_name']}.\n{describe_cart(c)}", "cart": c}
        if intent.action == "set_quantity":
            c = cart.set_quantity(session_id, product["id"], intent.quantity)
            return {"response": f"Updated {product['product_name']} to {intent.quantity}.\n{describe_cart(c)}", "cart": c}
        c = cart.add_item(session_id, product["id"], intent.quantity)
        return {"response": f"Added {intent.quantity} x {product['product_name']} to your cart.\n{describe_cart(c)}", "cart": c}
    except ValidationError as exc:
        return {"response": f"Sorry, {exc}.", "cart": cart.get_cart(session_id)}
