"""Test doubles for the network: a fake ``requests`` that serves recorded answers, and the contract every connector must meet."""
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return json.loads(text) if name.endswith(".json") else text


class Response:
    def __init__(self, body, status=200):
        self.status_code, self._body = status, body
        self.text = body if isinstance(body, str) else json.dumps(body)
        self.content = self.text.encode()

    def json(self):
        if isinstance(self._body, str):
            raise ValueError("not json")
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttp:
    """Serves ``routes`` ({url-prefix: body or (body, status)}) for GET and POST and records every call."""

    def __init__(self, routes: dict):
        self.routes, self.calls = routes, []

    def _answer(self, method, url, **kw):
        self.calls.append((method, url, kw))
        for prefix, answer in self.routes.items():
            if url.startswith(prefix):
                body, status = answer if isinstance(answer, tuple) else (answer, 200)
                return Response(body, status)
        return Response("not found", 404)

    def get(self, url, **kw):
        return self._answer("GET", url, **kw)

    def post(self, url, **kw):
        return self._answer("POST", url, **kw)


CARD_KEYS = {"id", "product_name", "brand", "category", "color", "size", "material", "price", "currency", "stock_quantity", "image_url", "description"}


def check_connector(store, *, query="kurta", expect_links=True):
    """What the page and the agent rely on, for any connector. Returns the cards it searched so a test can look further."""
    assert store.name and isinstance(store.capabilities, frozenset)
    found = store.search_products("contract", query, limit=4)
    assert set(found) >= {"products", "relaxed"} and isinstance(found["relaxed"], list)
    cards = found["products"]
    assert 0 < len(cards) <= 4
    for c in cards:
        assert CARD_KEYS <= set(c), CARD_KEYS - set(c)
        assert isinstance(c["product_name"], str) and c["product_name"].strip()
        assert isinstance(c["price"], (int, float)) and c["price"] > 0
        assert len(c["currency"]) == 3 and len(c["description"]) <= 240
        assert c["image_url"] is None or c["image_url"].startswith(("https://", "http://"))
        if c.get("catalogue_only") and expect_links:
            assert c["buy_url"] and c["buy_url"].startswith(("https://", "http://")), "a catalogue-only product needs a link to buy it"
    assert store.get_product("definitely-not-a-real-id-123") is None
    first = store.get_product(cards[0]["id"])
    assert first is None or first["product_name"] == cards[0]["product_name"]
    for odd in ("", "x" * 5000, "साड़ी 🧵", "'; DROP TABLE products;--", "kurta under 1000", "cheapest", "most expensive"):
        again = store.search_products("contract", odd, limit=3)
        assert isinstance(again["products"], list) and len(again["products"]) <= 3
    return cards
