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


def test_the_agent_returns_buy_links_for_a_connected_store():
    llm = Scripted(responses=[call("search_products", {"query": "silk saree"}), AIMessage(content="Try the Silk Saree.")], seen=[])
    r = run_agent("compare silk sarees", S, woo([WOO_ROW]), llm)
    assert r["products"][0]["buy_url"] == "https://shop.example/silk-saree" and "cart" not in r


def test_shopify_string_ids_flow_through_the_tools():
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


# ---- Fake Store API (free demo catalogue) ----
FAKE_ROWS = [
    {"id": 1, "title": "Fjallraven Backpack", "price": 109.95, "category": "men's clothing", "description": "A pack for the forest",
     "image": "https://fakestoreapi.com/img/1.png", "rating": {"rate": 3.9, "count": 120}},
    {"id": 2, "title": "Slim Fit T-Shirts", "price": 22.3, "category": "men's clothing", "description": "Casual cotton shirt",
     "image": "https://fakestoreapi.com/img/2.png", "rating": {"rate": 4.1, "count": 259}},
    {"id": 9, "title": "Gold Plated Ring", "price": 9.99, "category": "jewelery", "description": "A bright ring",
     "image": "javascript:alert(1)", "rating": {"rate": 4.6, "count": 400}},
]


def fake(rows=FAKE_ROWS, **kw):
    from zaldi.connectors.fakestore import FakeStore

    return FakeStore("https://fakestoreapi.com", http=FakeHttp(rows, **kw))


def test_fakestore_searches_titles_categories_and_applies_the_budget():
    store = fake()
    found = store.search_products(S, "show me men's clothing under 50", {"max_price": 50})["products"]
    assert [c["id"] for c in found] == [2]  # the backpack is over budget, the ring is the wrong category
    card = found[0]
    assert card["currency"] == "USD" and card["price"] == 22.3 and card["catalogue_only"] is True
    assert card["stock_quantity"] is None  # unknown, never claimed to be in stock


def test_fakestore_ranks_by_match_then_rating_and_strips_unsafe_images():
    ids = [c["id"] for c in fake().search_products(S, "ring")["products"]]
    assert ids == [9]
    assert fake().search_products(S, "ring")["products"][0]["image_url"] is None  # javascript: image dropped
    assert [c["id"] for c in fake().search_products(S, "")["products"]][0] == 9   # no terms: best rated first


def test_fakestore_reuses_its_product_list_and_survives_an_outage():
    from zaldi.connectors.fakestore import FakeStore

    http, now = FakeHttp(FAKE_ROWS), [0.0]
    store = FakeStore("https://fakestoreapi.com", http=http, clock=lambda: now[0])
    store.search_products(S, "ring"); store.search_products(S, "shirt")
    assert len(http.calls) == 1                                    # cached: one request for two questions
    now[0], http.fail = 10_000, True                               # cache expired and the API is down
    assert store.search_products(S, "ring")["products"]            # the stale list still answers
    with pytest.raises(ValidationError):
        FakeStore("https://fakestoreapi.com", http=FakeHttp([], fail=True)).search_products(S, "ring")


def test_fakestore_is_selectable_and_the_agent_sees_prices_with_their_currency(monkeypatch):
    get_connector.cache_clear()
    monkeypatch.setattr(config, "STORE_CONNECTOR", "fakestore")
    assert get_connector().name == "fakestore"
    get_connector.cache_clear()
    llm = Scripted(responses=[call("search_products", {"query": "shirt"}), AIMessage(content="The Slim Fit T-Shirts are $22.30.")], seen=[])
    r = run_agent("compare shirts", S, fake(), llm)
    sent = [m for m in llm.seen[1] if getattr(m, "tool_call_id", None)][0].content
    assert '"currency": "USD"' in sent and '"in_stock": "unknown"' in sent
    assert {t.name for t in build_tools(fake(), S, Run())} == {"search_products", "get_product", "ask_shopper"}
    assert r["products"][0]["catalogue_only"] is True
