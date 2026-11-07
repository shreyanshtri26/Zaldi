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


class MarketplaceServer:
    """A local server that speaks the *documented* Amazon Creators API and Flipkart Affiliate API protocols over real HTTP, so the
    connectors can be run end to end with the real ``requests`` library and no keys. It checks what a real marketplace would check
    (the token request, the bearer token, the marketplace header, the affiliate headers, the parameters) and records every request.

    Use as a context manager. ``amazon(...)`` and ``flipkart(...)`` build connectors already pointed at it."""

    AMAZON_SECRET, AMAZON_TOKEN = "good-secret", "tok-from-the-server"
    FLIPKART_ID, FLIPKART_TOKEN = "zaldi-aff", "good-token"

    def __enter__(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from urllib.parse import parse_qs, urlparse

        outer = self
        self.requests: list[dict] = []
        self.token_lifetime = 3600

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _json_body(self):
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    return json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    return None

            def do_POST(self):
                path, body = urlparse(self.path).path, self._json_body()
                outer.requests.append({"method": "POST", "path": path, "headers": dict(self.headers), "json": body})
                if path == "/auth/o2/token":
                    ok = (body and body.get("grant_type") == "client_credentials" and body.get("scope") == "creatorsapi::default"
                          and body.get("client_id") == "cred-id" and body.get("client_secret") == outer.AMAZON_SECRET
                          and "application/json" in (self.headers.get("Content-Type") or ""))
                    if ok:
                        return self._send(200, {"access_token": outer.AMAZON_TOKEN, "expires_in": outer.token_lifetime, "token_type": "Bearer"})
                    return self._send(401, {"error": "invalid_client"})
                if path in ("/catalog/v1/searchItems", "/catalog/v1/getItems"):
                    if self.headers.get("Authorization") != f"Bearer {outer.AMAZON_TOKEN}":
                        return self._send(401, {"errors": [{"code": "Unauthorized"}]})
                    if not self.headers.get("x-marketplace"):
                        return self._send(400, {"errors": [{"code": "MissingMarketplace"}]})
                    if not body or not body.get("partnerTag") or not (body.get("keywords") or body.get("itemIds")):
                        return self._send(400, {"errors": [{"code": "InvalidParameterValue"}]})
                    if path.endswith("searchItems"):
                        return self._send(200, fixture("amazon_search.json"))
                    wanted = body.get("itemIds") or []  # only the products it actually has; an unknown id simply is not in the answer
                    return self._send(200, {"itemsResult": {"items": [i for i in fixture("amazon_search.json")["searchResult"]["items"] if i.get("asin") in wanted]}})
                self._send(404, {})

            def do_GET(self):
                parsed = urlparse(self.path)
                query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                outer.requests.append({"method": "GET", "path": parsed.path, "headers": dict(self.headers), "query": query})
                if self.headers.get("Fk-Affiliate-Id") != outer.FLIPKART_ID or self.headers.get("Fk-Affiliate-Token") != outer.FLIPKART_TOKEN:
                    return self._send(403, {"error": "Unauthorized"})
                if parsed.path == "/affiliate/1.0/search.json":
                    if not query.get("query") or not 1 <= int(query.get("resultCount", "0") or 0) <= 10:
                        return self._send(400, {"error": "bad query"})
                    return self._send(200, fixture("flipkart_search.json"))
                if parsed.path == "/affiliate/1.0/product.json":
                    if query.get("id") == "SRIFKURTA1":
                        return self._send(200, fixture("flipkart_product.json"))
                    return self._send(404, {"error": "not found"})
                self._send(404, {})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def amazon(self, secret=None, marketplace="www.amazon.in"):
        from zaldi.connectors.amazon import AmazonStore

        return AmazonStore("cred-id", secret or self.AMAZON_SECRET, "zaldi-21", f"{self.url}/auth/o2/token", marketplace, api_base=self.url)

    def flipkart(self, token=None):
        from zaldi.connectors.flipkart import FlipkartStore

        return FlipkartStore(self.FLIPKART_ID, token or self.FLIPKART_TOKEN, api_base=f"{self.url}/affiliate")
