"""Amazon and Flipkart connectors talking to a local server that speaks their documented protocols, over real HTTP with the real
``requests`` library. Catches mistakes a fake cannot: header names, JSON bodies, query parameters, token handling."""
import pytest

from tests.fakes import MarketplaceServer, check_connector
from zaldi.errors import ValidationError


@pytest.fixture
def server():
    with MarketplaceServer() as s:
        yield s


def test_amazon_end_to_end_over_real_http(server):
    store = server.amazon()
    cards = check_connector(store, query="kurta")
    assert cards[0]["product_name"] == "Cotton Straight Kurta for Women" and cards[0]["price"] == 799.0 and "tag=zaldi-21" in cards[0]["buy_url"]
    token = next(r for r in server.requests if r["path"] == "/auth/o2/token")
    assert token["json"]["client_id"] == "cred-id" and "application/json" in token["headers"]["Content-Type"]
    search = next(r for r in server.requests if r["path"] == "/catalog/v1/searchItems")
    assert search["headers"]["Authorization"] == f"Bearer {server.AMAZON_TOKEN}" and search["headers"]["x-marketplace"] == "www.amazon.in"
    assert search["json"]["partnerTag"] == "zaldi-21" and search["json"]["keywords"] == "kurta" and 1 <= search["json"]["itemCount"] <= 10


def test_amazon_reuses_its_token_across_searches_and_signs_in_again_when_it_expires(server):
    store = server.amazon()
    store.search_products("s", "kurta")
    store.search_products("s", "saree")
    assert sum(r["path"] == "/auth/o2/token" for r in server.requests) == 1
    store._token = (0.0, "stale")  # the token has expired
    store._cache.clear()
    assert store.search_products("s", "dupatta")["products"] is not None
    assert sum(r["path"] == "/auth/o2/token" for r in server.requests) == 2


def test_amazon_with_a_wrong_secret_says_so_in_plain_words(server):
    with pytest.raises(ValidationError, match="sign in to Amazon"):
        server.amazon(secret="wrong").search_products("s", "kurta")


def test_amazon_get_product_over_real_http(server):
    assert server.amazon().get_product("B0KURTA001")["price"] == 799.0


def test_flipkart_end_to_end_over_real_http(server):
    store = server.flipkart()
    cards = check_connector(store, query="kurta")
    kurta = cards[0]
    assert kurta["product_name"] == "Chikankari Cotton Kurta" and kurta["price"] == 1199.0 and kurta["category"] == "Kurtas"
    call = next(r for r in server.requests if r["path"] == "/affiliate/1.0/search.json")
    assert call["query"] == {"query": "kurta", "resultCount": "10"}
    assert call["headers"]["Fk-Affiliate-Id"] == "zaldi-aff" and call["headers"]["Fk-Affiliate-Token"] == "good-token"


def test_flipkart_product_by_id_and_a_refused_token_over_real_http(server):
    assert server.flipkart().get_product("SRIFKURTA1")["product_name"] == "Chikankari Cotton Kurta"
    assert server.flipkart().get_product("nope") is None
    with pytest.raises(ValidationError, match="refused"):
        server.flipkart(token="wrong").search_products("s", "kurta")


def test_the_empty_query_the_test_button_sends_still_works_on_both(server):
    assert server.amazon().search_products("admin-test", "", limit=3)["products"]
    assert server.flipkart().search_products("admin-test", "", limit=3)["products"]
