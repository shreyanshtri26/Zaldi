"""WooCommerce and Shopify connectors against a fake HTTP layer (no network, no real store)."""
import pytest
from langchain_core.messages import AIMessage

from tests.test_agent_loop import Scripted, call
from zaldi import config
from zaldi.agent.loop import run_agent
from zaldi.agent.tools import Run, build_tools
from zaldi.connectors import base, get_connector
from zaldi.connectors.shopify import ShopifyStore
from zaldi.connectors.woocommerce import WooStore
from zaldi.db import init_db
from zaldi.errors import ValidationError
from zaldi.services import chat_service

S = "sess-conn-1"

WOO_ROW = {"id": 7, "name": "Silk Saree", "price": "4999.00", "stock_quantity": None, "stock_status": "instock",
           "permalink": "https://shop.example/silk-saree", "categories": [{"name": "Sarees"}],
           "images": [{"src": "https://shop.example/a.jpg"}],
           "short_description": "<p>Pure <b>silk</b> &amp; zari</p>",
           "attributes": [{"name": "Colour", "options": ["Red"]}, {"name": "Size", "options": ["Free", "M"]}]}


class Reply:
    def __init__(self, data, fail=False):
        self.data, self.fail = data, fail

    def raise_for_status(self):
        if self.fail:
            raise RuntimeError("boom https://secret-url token=abc")

    def json(self):
        return self.data


class FakeHttp:
    def __init__(self, data, fail=False):
        self.data, self.fail, self.calls = data, fail, []

    def get(self, url, **kw):
        self.calls.append(("get", url, kw))
        return Reply(self.data, self.fail)

    def post(self, url, **kw):
        self.calls.append(("post", url, kw))
        return Reply(self.data, self.fail)


def woo(data, **kw):
    return WooStore("https://shop.example/", "ck_1", "cs_1", http=FakeHttp(data, **kw))


def shopify(data, **kw):
    return ShopifyStore("demo.myshopify.com", "tok", "2025-07", http=FakeHttp(data, **kw))


SHOP_NODE = {"id": "gid://shopify/Product/1", "title": "Block Print Kurta", "vendor": "Jaipur Co", "productType": "Kurta",
             "description": "Cotton   kurta", "onlineStoreUrl": "https://demo.myshopify.com/products/kurta",
             "availableForSale": True, "featuredImage": {"url": "https://cdn.shopify.com/k.jpg"},
             "priceRange": {"minVariantPrice": {"amount": "1299.00", "currencyCode": "INR"}},
             "options": [{"name": "Size", "values": ["S", "M"]}, {"name": "Color", "values": ["Blue"]}]}


# ---- WooCommerce ----
def test_woocommerce_maps_a_product_to_a_card_and_links_out():
    store = woo([WOO_ROW])
    result = store.search_products(S, "silk saree", {"max_price": 5000})
    card = result["products"][0]
    assert card["id"] == 7 and card["price"] == 4999 and card["stock_quantity"] == 1
    assert card["color"] == "Red" and card["size"] == "Free, M" and card["category"] == "Sarees"
    assert card["description"] == "Pure silk & zari" and card["buy_url"] == "https://shop.example/silk-saree"
    _, url, kw = store.http.calls[0]
    assert url == "https://shop.example/wp-json/wc/v3/products" and kw["auth"] == ("ck_1", "cs_1")
    assert kw["params"]["search"] == "silk saree" and kw["params"]["max_price"] == 5000


def test_woocommerce_requires_https_and_credentials():
    with pytest.raises(ValueError):
        WooStore("http://shop.example", "k", "s")
    with pytest.raises(ValueError):
        WooStore("https://shop.example", "", "")


def test_a_failing_store_gives_a_plain_error_without_leaking_details():
    with pytest.raises(ValidationError) as err:
        woo([], fail=True).search_products(S, "saree")
    assert "not reachable" in str(err.value) and "secret-url" not in str(err.value) and "abc" not in str(err.value)


def test_woocommerce_get_product_handles_bad_ids():
    assert woo(WOO_ROW).get_product("abc") is None
    assert woo(WOO_ROW).get_product(7)["product_name"] == "Silk Saree"


# ---- Shopify ----
def test_shopify_maps_a_product_and_sends_the_token_in_a_header():
    store = shopify({"data": {"products": {"nodes": [SHOP_NODE]}}})
    card = store.search_products(S, "kurta")["products"][0]
    assert card["id"].startswith("gid://shopify/Product") and card["price"] == 1299 and card["stock_quantity"] == 1
    assert card["size"] == "S, M" and card["color"] == "Blue" and card["description"] == "Cotton kurta"
    _, url, kw = store.http.calls[0]
    assert url == "https://demo.myshopify.com/api/2025-07/graphql.json"
    assert kw["headers"]["X-Shopify-Storefront-Access-Token"] == "tok"


def test_shopify_applies_the_budget_itself():
    cheap, dear = dict(SHOP_NODE), dict(SHOP_NODE, id="gid://shopify/Product/2", priceRange={"minVariantPrice": {"amount": "9000.00"}})
    found = shopify({"data": {"products": {"nodes": [cheap, dear]}}}).search_products(S, "kurta", {"max_price": 2000})
    assert [c["price"] for c in found["products"]] == [1299]


def test_shopify_rejects_a_bad_domain_and_graphql_errors():
    with pytest.raises(ValueError):
        ShopifyStore("evil.example.com", "tok", "2025-07")
    with pytest.raises(ValidationError):
        shopify({"errors": [{"message": "Throttled"}]}).search_products(S, "kurta")


def test_links_must_be_plain_http():
    assert base.safe_url("javascript:alert(1)") is None and base.safe_url("data:text/html,x") is None
    assert base.safe_url("https://ok.example/p") == "https://ok.example/p"
    row = dict(WOO_ROW, permalink="javascript:alert(1)")
    assert woo([row]).search_products(S, "x")["products"][0]["buy_url"] is None


# ---- selection and agent behaviour ----
def test_the_connector_is_chosen_by_configuration(temp_db, monkeypatch):
    get_connector.cache_clear()
    monkeypatch.setattr(config, "STORE_CONNECTOR", "woocommerce")
    monkeypatch.setattr(config, "WOOCOMMERCE_URL", "https://shop.example")
    monkeypatch.setattr(config, "WOOCOMMERCE_KEY", "k")
    monkeypatch.setattr(config, "WOOCOMMERCE_SECRET", "s")
    assert get_connector().name == "woocommerce"
    get_connector.cache_clear()
    monkeypatch.setattr(config, "STORE_CONNECTOR", "nope")
    with pytest.raises(ValueError):
        get_connector()
    get_connector.cache_clear()


def test_a_read_only_store_gets_only_search_tools():
    names = {t.name for t in build_tools(woo([]), S, Run())}
    assert names == {"search_products", "get_product", "ask_shopper"}


def test_the_agent_returns_buy_links_for_a_connected_store(temp_db):
    init_db()  # the agent reads its prompts from the database; CI starts with none
    llm = Scripted(responses=[call("search_products", {"query": "silk saree"}), AIMessage(content="Try the Silk Saree.")], seen=[])
    r = run_agent("compare silk sarees", S, woo([WOO_ROW]), llm)
    assert r["products"][0]["buy_url"] == "https://shop.example/silk-saree" and "cart" not in r


def test_shopify_string_ids_flow_through_the_tools(temp_db):
    init_db()
    store = shopify({"data": {"product": SHOP_NODE}})
    llm = Scripted(responses=[call("get_product", {"product_id": "gid://shopify/Product/1"}), AIMessage(content="A blue kurta.")], seen=[])
    r = run_agent("tell me about it and compare", S, store, llm)
    assert r["steps"][0]["ok"] is True and r["products"][0]["product_name"] == "Block Print Kurta"


def test_a_connected_store_is_always_answered_by_the_agent_and_never_the_local_pipeline(temp_db, monkeypatch):
    init_db()
    chat_service.get_router.cache_clear()
    llm = Scripted(responses=[call("search_products", {"query": "kurta"}), AIMessage(content="Here is a kurta.")], seen=[])
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)
    monkeypatch.setattr("zaldi.connectors.get_connector", lambda: woo([WOO_ROW]))
    r = chat_service.handle_query("show me a kurta", S)  # no "compare" keyword: still the agent
    assert r["type"] == "agent" and r["products"][0]["id"] == 7


def test_a_connected_store_with_the_model_down_answers_from_its_own_catalogue_never_the_local_one(temp_db, monkeypatch):
    init_db()
    chat_service.get_router.cache_clear()

    class Boom(Scripted):
        def _generate(self, *a, **k):
            raise RuntimeError("quota")

    monkeypatch.setattr(chat_service, "get_llm", lambda: Boom(responses=[AIMessage(content="x")], seen=[]))
    monkeypatch.setattr("zaldi.connectors.get_connector", lambda: woo([WOO_ROW]))
    r = chat_service.handle_query("show me a silk saree", S)
    assert r["type"] == "products" and r["products"][0]["id"] == 7        # the WooCommerce product, not a local one
    assert "Silk Saree" in r["response"] and "Rs. 4,999" in r["response"]


# ---- Platzi Fake Store API (api.escuelajs.co): free demo catalogue ----
ROWS = [
    {"id": 1, "title": "Mountain T-Shirt", "price": 44, "description": "Soft cotton tee", "images": ["https://i.imgur.com/a.jpeg"], "category": {"id": 1, "name": "mylove"}},
    {"id": 2, "title": "Leather Shoes", "price": 120, "description": "Classic shoes", "images": ['["https://i.imgur.com/b.jpeg"]'], "category": {"id": 4, "name": "Shoes"}},
    {"id": 3, "title": "Cheap Sneakers", "price": 15, "description": "Light shoes", "images": ["https://placehold.co/600x400?img=3"], "category": {"id": 4, "name": "Shoes"}},
    {"id": 4, "title": "Broken Item", "price": 0, "description": "price is zero", "images": [], "category": {"id": 5, "name": "Misc"}},
    {"id": 5, "title": "Gadget", "price": 99, "description": "A gadget", "images": [], "category": {"id": 2, "name": "Electronics "}},
]


class EscuelaHttp(FakeHttp):
    """Serves GET /products (offset/limit paging) and GET /products/{id} from one list."""

    def get(self, url, **kw):
        self.calls.append(("get", url, kw))
        path, params = url.split("api.escuelajs.co/api/v1", 1)[-1], kw.get("params") or {}
        if path == "/products":
            start = params.get("offset", 0)
            data = self.data[start:start + params.get("limit", 100)]
        else:
            data = next((r for r in self.data if r["id"] == int(path.rsplit("/", 1)[1])), {})
        return Reply(data, self.fail)


def escuela(rows=ROWS, **kw):
    from zaldi.connectors.escuelajs import EscuelaStore

    return EscuelaStore("https://api.escuelajs.co/api/v1", http=EscuelaHttp(rows, **kw))


def found(store, query, **filters):
    return [c["id"] for c in store.search_products(S, query, filters or None)["products"]]


def test_escuela_cleans_up_the_apis_quirks():
    store = escuela()
    shoes, sneakers = store.get_product(2), store.get_product(3)
    assert shoes["image_url"] == "https://i.imgur.com/b.jpeg"          # a URL hidden inside JSON-looking text
    assert sneakers["image_url"] == "https://placehold.co/600x400?img=3"  # the API sent only a placeholder box: show it as sent
    assert shoes["currency"] == "USD" and shoes["stock_quantity"] is None and shoes["catalogue_only"] is True
    assert store.get_product(4) is None                                 # a zero price is not a sellable product
    both = dict(ROWS[1], id=9, images=["https://placehold.co/1x1", "https://i.imgur.com/real.jpeg"])
    assert escuela([both]).get_product(9)["image_url"] == "https://i.imgur.com/real.jpeg"   # a real photo wins over a placeholder
    assert all(escuela([dict(ROWS[1], id=8, images=["https://example.com/x.png"])]).get_product(8)["image_url"] == "https://example.com/x.png" for _ in [0])  # whatever the API sent
    assert store.get_product("abc") is None


def test_escuela_categories_are_trimmed_counted_and_skip_junk_products():
    cats = escuela().list_categories()
    assert {c["name"]: c["count"] for c in cats} == {"Shoes": 2, "mylove": 1, "Electronics": 1}   # "Misc" held only the zero-price item
    assert cats[0]["name"] == "Shoes"                                   # most stocked first


def test_escuela_matches_a_named_category_and_understands_ordering():
    store = escuela()
    assert sorted(found(store, "show me shoes")) == [2, 3]
    assert found(store, "cheapest shoes") == [3, 2]
    assert found(store, "most expensive shoes") == [2, 3]
    assert found(store, "show me the cheapest")[0] == 3                 # ordering with nothing else named: whole catalogue
    assert found(store, "show me", max_price=50) == [1, 3]               # budget filter, nothing else named


def test_escuela_prefers_the_longest_category_name():
    rows = [dict(ROWS[1], id=10, category={"name": "Running Shoes"}, title="Trail Runner"), dict(ROWS[1], id=11, title="Office Shoe")]
    assert found(escuela(rows), "running shoes") == [10]               # not mixed with plain "Shoes"


def test_escuela_pages_through_the_catalogue_and_reuses_what_it_fetched(monkeypatch):
    from zaldi.connectors import escuelajs

    monkeypatch.setattr(escuelajs, "PAGE", 2)
    store = escuela()
    assert [r["id"] for r in store._all()] == [1, 2, 3, 5]             # 5 rows read as 3 pages of 2; the zero-price one dropped; no duplicates
    first = len(store.http.calls)
    store.search_products(S, "shoes"); store.search_products(S, "gadget")
    assert first == 3 and len(store.http.calls) == first               # cached: no further requests


def test_escuela_survives_an_outage_with_its_cached_list_and_never_leaks_details():
    from zaldi.connectors.escuelajs import EscuelaStore

    http, now = EscuelaHttp(ROWS), [0.0]
    store = EscuelaStore("https://api.escuelajs.co/api/v1", http=http, clock=lambda: now[0])
    assert found(store, "shoes")
    now[0], http.fail = 10_000, True                                    # cache expired, API down
    assert found(store, "shoes")                                        # the stale list still answers
    with pytest.raises(ValidationError) as err:
        EscuelaStore("https://api.escuelajs.co/api/v1", http=EscuelaHttp([], fail=True)).search_products(S, "x")
    assert "not reachable" in str(err.value) and "secret-url" not in str(err.value)


def test_escuela_is_selectable_and_agent_gets_search_tools_only(monkeypatch, temp_db):
    get_connector.cache_clear()
    monkeypatch.setattr(config, "STORE_CONNECTOR", "escuelajs")
    assert get_connector().name == "escuelajs"
    get_connector.cache_clear()
    assert {t.name for t in build_tools(escuela(), S, Run())} == {"search_products", "get_product", "ask_shopper"}


def test_a_connected_escuela_store_answers_in_plain_text_with_followup_chips_when_the_model_is_down(temp_db, monkeypatch):
    init_db()
    chat_service.get_router.cache_clear()

    class Boom(Scripted):
        def _generate(self, *a, **k):
            raise RuntimeError("quota")

    monkeypatch.setattr(chat_service, "get_llm", lambda: Boom(responses=[AIMessage(content="x")], seen=[]))
    monkeypatch.setattr("zaldi.connectors.get_connector", lambda: escuela())
    r = chat_service.handle_query("show me shoes", S)
    assert "Cheap Sneakers - $15.00" in r["response"] and "Lowest price: Cheap Sneakers ($15.00)" in r["response"]
    assert "Top rated" not in r["response"]                             # this API has no ratings, so none is invented
    assert r["quick_replies"] == ["Cheapest Shoes"]
