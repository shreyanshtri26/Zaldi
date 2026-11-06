"""The built-in store: the SQLite catalogue, the FAISS/lexical search, the policy index and the session cart."""
from dataclasses import replace

from zaldi.connectors.base import CART, CHECKOUT, POLICIES, PREFERENCES, SEARCH, sort_intent
from zaldi.db import connect
from zaldi.errors import ValidationError
from zaldi.search.extract import extract_filters, merge_defaults
from zaldi.search.hybrid import search
from zaldi.services import cart, preferences

CARD_FIELDS = ("id", "product_name", "brand", "category", "color", "size", "material", "price", "stock_quantity",
               "image_url", "description")
DESCRIPTION_LIMIT = 240  # product text is data from the store; keep what reaches the model short


def _card(row: dict) -> dict:
    card = {k: row.get(k) for k in CARD_FIELDS}
    card["description"] = (card["description"] or "")[:DESCRIPTION_LIMIT]
    return card


def _pid(product_id) -> int:
    try:
        return int(product_id)
    except (TypeError, ValueError):
        raise ValidationError("that product does not exist") from None


class LocalStore:
    name = "local"
    capabilities = frozenset({SEARCH, POLICIES, CART, PREFERENCES, CHECKOUT})

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        found = merge_defaults(extract_filters(query), preferences.preference_filters(session_id))
        extra = {k: v for k, v in (filters or {}).items() if k in ("max_price", "min_price", "category") and v}
        found = replace(found, **extra)
        sort = (filters or {}).get("sort") or sort_intent(query)
        if sort in ("price_asc", "price_desc"):  # order the whole filtered set, not just the top few by relevance
            rows, relaxed = search(query, found, limit=50)
            rows = sorted(rows, key=lambda r: r["price"], reverse=sort == "price_desc")[:limit]
        else:
            rows, relaxed = search(query, found, limit=limit)
        cart.remember_results(session_id, [r["id"] for r in rows])
        return {"products": [_card(r) for r in rows], "relaxed": relaxed}

    def get_product(self, product_id: int) -> dict | None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM products WHERE id = ?", (_pid(product_id),)).fetchone()
        return _card(dict(row)) if row else None

    def list_categories(self) -> list[dict]:
        kids = {"Boys": "Kids", "Girls": "Kids"}
        with connect() as conn:
            rows = conn.execute("SELECT category, gender, COUNT(*) AS n FROM products GROUP BY category, gender").fetchall()
        by_category: dict[str, dict] = {}
        for r in rows:
            entry = by_category.setdefault(r["category"], {"count": 0, "genders": {}})
            entry["count"] += r["n"]
            group = kids.get(r["gender"], r["gender"] or "More")
            entry["genders"][group] = entry["genders"].get(group, 0) + r["n"]
        out = [{"name": name, "count": e["count"], "group": max(e["genders"], key=e["genders"].get)} for name, e in by_category.items()]
        return sorted(out, key=lambda c: (-c["count"], c["name"]))  # most stocked first

    def search_policies(self, query: str, k: int = 3) -> list[str]:
        from zaldi.ai.tools.policy_search import search_policies

        return search_policies(query, k=k)

    def cart_view(self, session_id: str) -> dict:
        return cart.get_cart(session_id)

    def cart_add(self, session_id: str, product_id: int, quantity: int = 1) -> dict:
        return cart.add_item(session_id, _pid(product_id), quantity)

    def cart_remove(self, session_id: str, product_id: int) -> dict:
        return cart.remove_item(session_id, _pid(product_id))

    def save_preference(self, session_id: str, changes: dict) -> dict:
        current = preferences.get_preferences(session_id)
        current.update({k: v for k, v in changes.items() if v not in (None, "")})
        return preferences.save_preferences(session_id, current)

    def start_checkout(self, session_id: str) -> dict:
        c = cart.get_cart(session_id)
        if not c["items"]:
            return {"error": "the cart is empty"}
        # The delivery address is collected by a secure form in the UI, never by the chat or the model.
        return {"cart": c, "action": "collect_address"}
