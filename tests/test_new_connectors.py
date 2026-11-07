"""Feed, custom API, link-page, Amazon and Flipkart connectors, run against recorded responses: the shared contract, then each one's own rules."""
import json

import pytest

from tests.fakes import FIXTURES, FakeHttp, check_connector, fixture
from zaldi.connectors import build_connector, feed, netguard
from zaldi.connectors.amazon import AmazonStore
from zaldi.connectors.base import capability_level
from zaldi.connectors.feed import FeedStore
from zaldi.connectors.flipkart import FlipkartStore
from zaldi.connectors.linkpage import LinkStore, parse_page
from zaldi.connectors.rest import RestStore, validate
from zaldi.errors import ValidationError
from zaldi.services import onboarding


@pytest.fixture(autouse=True)
def allow_test_hosts(monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_STORE_URLS", "1")  # the fake hosts do not resolve


# --- feed ---------------------------------------------------------------------------------------------------------------------------
def test_feed_meets_the_contract_and_reads_a_google_style_csv():
    store = FeedStore(str(FIXTURES / "feed.csv"), label="Demo feed")
    cards = check_connector(store, query="saree")
    assert {c["product_name"] for c in cards} == {"Banarasi Silk Saree", "Georgette Party Saree"}
    silk = next(c for c in cards if c["product_name"].startswith("Banarasi"))
    assert (silk["price"], silk["currency"], silk["brand"], silk["category"], silk["source"]) == (6499.0, "INR", "Banaras Weaves", "Sarees", "Demo feed")
    assert next(c for c in cards if c["product_name"].startswith("Georgette"))["stock_quantity"] == 0  # "out of stock" is kept, not hidden
    assert store.skipped_rows == 2  # a row with no title and a row with no price


def test_feed_filters_budget_and_orders_by_price():
    store = FeedStore(str(FIXTURES / "feed.csv"))
    assert [c["product_name"] for c in store.search_products("s", "saree", {"max_price": 3000})["products"]] == ["Georgette Party Saree"]
    assert [c["product_name"] for c in store.search_products("s", "cheapest")["products"]][0] == "Leather Jutti"
    assert [c["product_name"] for c in store.search_products("s", "most expensive")["products"]][0] == "Banarasi Silk Saree"


def test_feed_reads_json_in_several_shapes_and_tab_separated_text():
    row = {"sku": "A1", "name": "Wool Shawl", "price": "1,500", "url": "https://x.test/a1", "images": ["https://x.test/a1.jpg"]}
    for payload in (json.dumps([row]), json.dumps({"products": [row]}), json.dumps({"items": [row]})):
        cards, skipped = feed.parse(payload)
        assert (len(cards), skipped, cards[0]["price"], cards[0]["image_url"]) == (1, 0, 1500.0, "https://x.test/a1.jpg")
    cards, _ = feed.parse("id\ttitle\tprice\tlink\nT1\tTab Shawl\t300\thttps://x.test/t1")
    assert cards[0]["product_name"] == "Tab Shawl"


def test_feed_over_http_uses_a_cached_copy_and_survives_an_outage():
    http = FakeHttp({"https://shop.test/feed.csv": fixture("feed.csv")})
    now = {"t": 0}
    store = FeedStore("https://shop.test/feed.csv", http=http, clock=lambda: now["t"])
    store.search_products("s", "kurta")
    store.search_products("s", "saree")
    assert len(http.calls) == 1  # the second question cost no request
    now["t"] = 10_000
    http.routes = {"https://shop.test/feed.csv": ("down", 500)}
    assert store.search_products("s", "kurta")["products"]  # stale copy beats a failed question
    with pytest.raises(ValidationError):
        FeedStore("https://shop.test/feed.csv", http=http).search_products("s", "kurta")


def test_a_feed_pointing_at_the_servers_own_network_is_refused(monkeypatch):
    monkeypatch.delenv("ALLOW_PRIVATE_STORE_URLS")
    for bad in ("http://127.0.0.1/feed.csv", "http://localhost:5000/x", "http://169.254.169.254/latest/meta-data", "http://10.0.0.5/feed", "ftp://x.test/f"):
        with pytest.raises(ValidationError):
            netguard.check_public_url(bad)


# --- custom API -----------------------------------------------------------------------------------------------------------------------
MAPPING = {"search_url": "https://api.shop.test/search?q={query}&n={limit}", "product_url": "https://api.shop.test/p/{id}", "items_path": "data.items",
           "headers": {"Authorization": "Bearer abc"}, "currency": "INR", "label": "Shop API",
           "fields": {"id": "sku", "name": "title", "price": "pricing.sale", "currency": "pricing.cur", "image": "images.0", "url": "links.web",
                      "category": "cat.name", "brand": "brand", "description": "about", "rating": "stars", "in_stock": "available"}}
API_ROWS = {"data": {"items": [
    {"sku": "r1", "title": "Silk Kurta", "pricing": {"sale": 2400, "cur": "INR"}, "images": ["https://cdn.test/r1.jpg"], "links": {"web": "https://shop.test/r1"},
     "cat": {"name": "Kurtas"}, "brand": "Weave", "about": "Pure silk", "stars": 4.5, "available": True},
    {"sku": "r2", "title": "Cotton Kurta", "pricing": {"sale": 900, "cur": "INR"}, "images": [], "links": {"web": "https://shop.test/r2"},
     "cat": {"name": "Kurtas"}, "about": "Daily wear", "available": False},
    {"sku": "r3", "title": "Broken", "pricing": {}, "links": {"web": "https://shop.test/r3"}},
]}}


def rest_store():
    return RestStore(MAPPING, http=FakeHttp({"https://api.shop.test/search": API_ROWS, "https://api.shop.test/p/r1": API_ROWS["data"]["items"][0]}))


def test_custom_api_meets_the_contract_maps_fields_and_sends_the_headers():
    store = rest_store()
    cards = check_connector(store, query="kurta")
    assert [c["product_name"] for c in cards] == ["Silk Kurta", "Cotton Kurta"]  # the row with no price is dropped
    assert (cards[0]["rating"], cards[0]["source"]) == (4.5, "Shop API") and cards[1]["stock_quantity"] == 0
    assert store.http.calls[0][2]["headers"] == {"Authorization": "Bearer abc"}
    assert store.get_product("r1")["product_name"] == "Silk Kurta"


def test_the_api_mapping_is_validated_with_messages_an_admin_can_act_on():
    for broken, message in (({"fields": {}}, "search_url"), ({"search_url": "https://x/{query}", "fields": {"id": "a"}}, "id, name and price"),
                            ({"search_url": "https://x/{query}", "fields": {"id": "a", "name": "b", "price": "c"}, "product_url": "https://x/p"}, "{id}"), ("[]", "JSON object")):
        with pytest.raises(ValueError, match=message):
            validate(broken)


def test_api_search_words_are_url_encoded():
    store = rest_store()
    store.search_products("s", "red & blue/kurta?x=1")
    assert "red%20%26%20blue%2Fkurta%3Fx%3D1" in store.http.calls[0][1]


# --- link pages -----------------------------------------------------------------------------------------------------------------------
def test_a_product_page_is_read_from_its_schema_org_data():
    card = parse_page(fixture("product_page.html"), "https://shop.test/saree", "Weaver")
    assert (card["product_name"], card["price"], card["currency"], card["brand"], card["rating"], card["rating_count"]) == \
           ("Handloom Cotton Saree", 1799.0, "INR", "Weaver Co", 4.4, 128)
    assert card["description"] == "Soft handloom saree for daily wear" and card["buy_url"] == "https://shop.test/saree" and card["image_url"].endswith("saree.jpg")


def test_open_graph_tags_are_the_fallback_and_a_page_without_a_product_gives_nothing():
    assert parse_page(fixture("og_page.html"), "https://shop.test/car")["price"] == 349.0
    assert parse_page("<html><body>About us</body></html>", "https://shop.test/about") is None


def test_link_store_meets_the_contract_and_reports_pages_it_could_not_use():
    pages = {"https://shop.test/robots.txt": ("User-agent: *\nDisallow: /private", 200), "https://shop.test/saree": fixture("product_page.html"),
             "https://shop.test/about": "<html>no product</html>", "https://shop.test/private/x": fixture("product_page.html")}
    store = LinkStore("https://shop.test/saree https://shop.test/about https://shop.test/private/x", http=FakeHttp(pages), check_url=lambda u: u)
    cards = check_connector(store, query="saree")
    assert [c["product_name"] for c in cards] == ["Handloom Cotton Saree"]
    problems = " ".join(store.problems)
    assert "no product name and price" in problems and "robots.txt" in problems


def test_amazon_and_flipkart_pages_are_not_read_directly():
    for url in ("https://www.amazon.in/dp/B0X", "https://www.flipkart.com/p/x", "https://amzn.in/abc"):
        with pytest.raises(ValueError, match="affiliate"):
            LinkStore(url)
    with pytest.raises(ValueError, match="at least one"):
        LinkStore("")


# --- Amazon -------------------------------------------------------------------------------------------------------------------------------
EU_TOKEN = "https://api.amazon.co.uk/auth/o2/token"  # the token address for India in Amazon's documentation
SEARCH_URL = "https://creatorsapi.amazon/catalog/v1/searchItems"


def amazon_store(marketplace="www.amazon.in", token_url="", **routes):
    http = FakeHttp({EU_TOKEN: {"access_token": "tok-1", "expires_in": 3600}, SEARCH_URL: fixture("amazon_search.json"), **routes})
    return AmazonStore("cred-id", "cred-secret", "zaldi-21", token_url, marketplace, http=http), http


class Sequence(FakeHttp):
    """Answers each URL from a list, one answer per call, so a test can script a 401 followed by a success."""

    def __init__(self, answers):
        super().__init__({})
        self.answers = {k: list(v) for k, v in answers.items()}

    def _answer(self, method, url, **kw):
        from tests.fakes import Response

        self.calls.append((method, url, kw))
        body, status = self.answers[url].pop(0) if len(self.answers[url]) > 1 else self.answers[url][0]
        return Response(body, status)


def test_amazon_meets_the_contract_and_reads_the_documented_response():
    store, http = amazon_store()
    cards = check_connector(store, query="kurta")
    kurta = next(c for c in cards if c["product_name"].startswith("Cotton Straight"))
    assert kurta["source"] == "Amazon" and kurta["buy_url"] == "https://www.amazon.in/dp/B0KURTA001?tag=zaldi-21&linkCode=osi"  # detailPageURL, with the tag
    assert (kurta["price"], kurta["currency"], kurta["brand"]) == (799.0, "INR", "Jaipur Prints")  # the buy-box winner's price, not the first listing's
    assert kurta["image_url"].endswith("kurta-large.jpg") and "Machine washable" in kurta["description"] and kurta["stock_quantity"] is None


def test_amazon_falls_back_to_a_smaller_picture_marks_sold_out_items_and_drops_items_without_an_offer():
    store, _ = amazon_store()
    by_name = {c["product_name"]: c for c in store.search_products("s", "")["products"]}
    assert by_name["Banarasi Silk Saree with Blouse Piece"]["image_url"].endswith("saree-medium.jpg")
    assert by_name["Printed Cotton Dupatta"]["stock_quantity"] == 0 and by_name["Printed Cotton Dupatta"]["image_url"] is None
    assert by_name["Handloom Cotton Stole"]["price"] == 499.0  # the retired PA-API spelling is still understood
    assert "Item without an offer" not in by_name and len(by_name) == 4


def test_amazon_signs_in_with_the_documented_request_and_sends_the_documented_search():
    store, http = amazon_store()
    store.search_products("s", "kurta")
    token_call = next(c for c in http.calls if c[1] == EU_TOKEN)
    assert token_call[2]["json"] == {"grant_type": "client_credentials", "client_id": "cred-id", "client_secret": "cred-secret", "scope": "creatorsapi::default"}
    assert token_call[2]["headers"]["Content-Type"] == "application/json"
    search = next(c for c in http.calls if c[1] == SEARCH_URL)
    assert search[2]["headers"] == {"Authorization": "Bearer tok-1", "x-marketplace": "www.amazon.in", "Content-Type": "application/json"}
    body = search[2]["json"]
    assert (body["keywords"], body["partnerTag"], body["marketplace"], body["itemCount"]) == ("kurta", "zaldi-21", "www.amazon.in", 10)
    assert "images.primary.large" in body["resources"] and "offersV2.listings.price" in body["resources"] and "sortBy" not in body


def test_amazon_asks_for_the_sort_and_price_range_in_the_currencys_smallest_unit():
    store, http = amazon_store()
    store.search_products("s", "kurta", {"sort": "price_asc", "min_price": 500, "max_price": 4000})
    body = next(c for c in http.calls if c[1] == SEARCH_URL)[2]["json"]
    assert (body["sortBy"], body["minPrice"], body["maxPrice"]) == ("Price:LowToHigh", 50000, 400000)  # rupees to paise
    for intent, name in (("price_desc", "Price:HighToLow"), ("rating", "AvgCustomerReviews")):
        s2, h2 = amazon_store()
        s2.search_products("s", "kurta", {"sort": intent})
        assert next(c for c in h2.calls if c[1] == SEARCH_URL)[2]["json"]["sortBy"] == name
    yen, h3 = amazon_store("www.amazon.co.jp", **{TOKEN_FE: {"access_token": "t", "expires_in": 3600}})
    yen.search_products("s", "kurta", {"max_price": 4000})
    assert next(c for c in h3.calls if c[1] == SEARCH_URL)[2]["json"]["maxPrice"] == 4000  # yen has no smaller unit


TOKEN_FE = "https://api.amazon.co.jp/auth/o2/token"


@pytest.mark.parametrize("marketplace, expected", [
    ("www.amazon.in", "https://api.amazon.co.uk/auth/o2/token"), ("www.amazon.co.uk", "https://api.amazon.co.uk/auth/o2/token"), ("www.amazon.de", "https://api.amazon.co.uk/auth/o2/token"),
    ("www.amazon.com", "https://api.amazon.com/auth/o2/token"), ("www.amazon.ca", "https://api.amazon.com/auth/o2/token"), ("www.amazon.com.br", "https://api.amazon.com/auth/o2/token"),
    ("www.amazon.co.jp", "https://api.amazon.co.jp/auth/o2/token"), ("www.amazon.com.au", "https://api.amazon.co.jp/auth/o2/token"), ("www.amazon.sg", "https://api.amazon.co.jp/auth/o2/token"),
    ("www.amazon.unknown", "https://api.amazon.com/auth/o2/token"),
])
def test_the_token_address_follows_the_marketplaces_region_unless_one_is_given(marketplace, expected):
    from zaldi.connectors.amazon import token_url_for

    assert token_url_for(marketplace) == expected
    assert AmazonStore("a", "b", "c", "", marketplace).token_url == expected
    assert AmazonStore("a", "b", "c", "https://auth.example.test/token", marketplace).token_url == "https://auth.example.test/token"


def test_amazon_signs_in_once_and_signs_in_again_if_the_token_was_refused():
    store, http = amazon_store()
    store.search_products("s", "kurta")
    store.search_products("s", "saree")
    assert sum(c[1] == EU_TOKEN for c in http.calls) == 1 and sum(c[1] == SEARCH_URL for c in http.calls) == 2
    seq = Sequence({EU_TOKEN: [({"access_token": "old", "expires_in": 3600}, 200), ({"access_token": "new", "expires_in": 3600}, 200)],
                    SEARCH_URL: [("expired", 401), (fixture("amazon_search.json"), 200)]})
    again = AmazonStore("a", "b", "tag", "", "www.amazon.in", http=seq)
    assert again.search_products("s", "kurta")["products"]
    assert sum(c[1] == EU_TOKEN for c in seq.calls) == 2 and [c[2]["headers"]["Authorization"] for c in seq.calls if c[1] == SEARCH_URL] == ["Bearer old", "Bearer new"]


def test_amazon_repeats_no_request_it_has_just_made_and_explains_bad_credentials():
    store, http = amazon_store()
    store.search_products("s", "kurta")
    store.search_products("s", "kurta")
    assert sum(c[1] == SEARCH_URL for c in http.calls) == 1
    refused, _ = amazon_store(**{EU_TOKEN: ("denied", 401)})
    with pytest.raises(ValidationError, match="sign in to Amazon"):
        refused.search_products("s", "kurta")
    with pytest.raises(ValueError, match="required"):
        AmazonStore("", "", "")


def test_amazon_get_product_by_asin_and_a_failure_is_just_not_found():
    store, _ = amazon_store(**{"https://creatorsapi.amazon/catalog/v1/getItems": {"itemsResult": {"items": fixture("amazon_search.json")["searchResult"]["items"][:1]}}})
    assert store.get_product("B0KURTA001")["price"] == 799.0
    assert amazon_store(**{"https://creatorsapi.amazon/catalog/v1/getItems": ("x", 500)})[0].get_product("B0") is None


# --- Flipkart -------------------------------------------------------------------------------------------------------------------------------
FK = "https://affiliate-api.flipkart.net/affiliate"


class FlipkartHttp(FakeHttp):
    """Like the real API, the product endpoint knows one product and answers 404 for any other id."""

    def get(self, url, **kw):
        if url.endswith("/1.0/product.json") and kw.get("params", {}).get("id") != "SRIFKURTA1" and not isinstance(self.routes.get(url), tuple):
            self.calls.append(("GET", url, kw))
            from tests.fakes import Response

            return Response("not found", 404)
        return super().get(url, **kw)


def flipkart_store(**routes):
    http = FlipkartHttp({f"{FK}/1.0/search.json": fixture("flipkart_search.json"), f"{FK}/1.0/product.json": fixture("flipkart_product.json"), **routes})
    return FlipkartStore("zaldi-aff", "secret-token", http=http), http


def test_flipkart_meets_the_contract_and_reads_the_documented_response():
    store, http = flipkart_store()
    cards = check_connector(store, query="kurta")
    kurta = next(c for c in cards if "Kurta" in c["product_name"])
    assert (kurta["price"], kurta["category"], kurta["brand"], kurta["source"], kurta["color"], kurta["size"]) == (1199.0, "Kurtas", "Lucknowi Loom", "Flipkart", "White", "M")
    assert kurta["image_url"].endswith("/800/kurta.jpeg") and kurta["buy_url"].endswith("affid=zaldi")  # the special price, the biggest picture, the untouched affiliate link
    assert kurta["description"] == "Hand embroidered straight kurta" and kurta["stock_quantity"] is None


def test_flipkart_sends_the_documented_search_with_the_affiliate_headers():
    store, http = flipkart_store()
    store.search_products("s", "kurta")
    call = http.calls[0]
    assert call[1] == f"{FK}/1.0/search.json" and call[2]["params"] == {"query": "kurta", "resultCount": 10}
    assert call[2]["headers"] == {"Fk-Affiliate-Id": "zaldi-aff", "Fk-Affiliate-Token": "secret-token"}


def test_flipkart_handles_special_prices_missing_pictures_stock_and_the_legacy_shape():
    store, _ = flipkart_store()
    by_name = {c["product_name"]: c for c in store.search_products("s", "")["products"]}
    saree = by_name["Kanjivaram Silk Saree"]
    assert saree["price"] == 6499.0 and saree["stock_quantity"] == 0 and saree["category"] == "Sarees" and saree["image_url"].endswith("/unknown/saree.jpeg")
    jutti = by_name["Handmade Leather Jutti"]  # the older response shape
    assert (jutti["id"], jutti["price"], jutti["category"], jutti["color"], jutti["size"], jutti["brand"]) == ("LEGACYJUTTI3", 599.0, "Juttis", "Brown", "8", "Kolhapur Craft")
    assert "Item without a price" not in by_name and len(by_name) == 3


def test_flipkart_get_product_uses_the_current_endpoint_and_a_failure_is_just_not_found():
    store, http = flipkart_store()
    card = store.get_product("SRIFKURTA1")
    assert card["product_name"] == "Chikankari Cotton Kurta" and card["price"] == 1199.0
    call = http.calls[0]
    assert call[1] == f"{FK}/1.0/product.json" and call[2]["params"] == {"id": "SRIFKURTA1"}
    assert flipkart_store(**{f"{FK}/1.0/product.json": ("nope", 404)})[0].get_product("x") is None


def test_flipkart_explains_a_refused_token_and_remembers_a_search_it_just_made():
    store, http = flipkart_store()
    store.search_products("s", "kurta")
    store.search_products("s", "kurta")
    assert len(http.calls) == 1
    with pytest.raises(ValidationError, match="refused"):
        FlipkartStore("a", "b", http=FakeHttp({FK: ("no", 403)})).search_products("s", "kurta")
    with pytest.raises(ValueError, match="required"):
        FlipkartStore("", "")


# --- wiring + the admin's Test checklist -----------------------------------------------------------------------------------------------------
def test_every_connector_is_built_from_settings_and_declares_its_level():
    values = {"feed_url": str(FIXTURES / "feed.csv"), "rest_config": json.dumps(MAPPING), "link_urls": "https://shop.test/a",
              "amazon_credential_id": "i", "amazon_credential_secret": "s", "amazon_partner_tag": "t",
              "flipkart_affiliate_id": "a", "flipkart_token": "t"}
    built = {k: build_connector({"connector": k, **values}) for k in ("feed", "rest", "links", "amazon", "flipkart")}
    assert {k: v.name for k, v in built.items()} == {"feed": "feed", "rest": "rest", "links": "links", "amazon": "amazon", "flipkart": "flipkart"}
    assert all(capability_level(v.capabilities) == "catalogue" for v in built.values())
    with pytest.raises(ValueError, match="unknown store connector"):
        build_connector({"connector": "magento"})


def test_the_test_checklist_passes_a_healthy_feed_and_explains_a_broken_one():
    good = onboarding.check(FeedStore(str(FIXTURES / "feed.csv")))
    assert good["ok"] and good["level"] == "catalogue" and good["found"] == 4
    assert {c["name"] for c in good["checks"]} >= {"Store answers", "Products found", "Prices are valid", "Rows usable"}
    assert next(c for c in good["checks"] if c["name"] == "Rows usable")["fix"]
    broken = onboarding.check(FeedStore("https://shop.test/missing.csv", http=FakeHttp({})))
    assert not broken["ok"] and broken["checks"][0]["ok"] is False and broken["checks"][0]["fix"]
