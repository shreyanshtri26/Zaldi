"""Home-page categories: they come from the connected store, tapping each one finds its products, and the admin can trim them."""
import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from tests.helpers import ADMIN_HEADERS
from tests.test_connectors import FAKE_ROWS, FakeHttp, WOO_ROW, woo
from zaldi.connectors.fakestore import FakeStore
from zaldi.connectors.local import LocalStore
from zaldi.db import connect, init_db
from zaldi.services import chat_service

S = "sess-cats-1"
GROUPS = {"Women", "Men", "Kids", "Unisex", "More"}


@pytest.fixture(autouse=True)
def env(temp_db, monkeypatch):
    init_db()
    chat_service.get_router.cache_clear()
    llm = FakeListChatModel(responses=["Here are some options."] * 60)
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)
    monkeypatch.setattr("zaldi.ai.models.get_llm", lambda: llm)


def test_local_categories_cover_the_whole_catalogue_most_stocked_first():
    cats = LocalStore().list_categories()
    with connect() as conn:
        assert sum(c["count"] for c in cats) == conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    assert [c["count"] for c in cats] == sorted((c["count"] for c in cats), reverse=True) and {c["group"] for c in cats} <= GROUPS


def test_the_categories_endpoint_is_public_and_shows_six_by_default(client):
    body = client.get("/api/categories").get_json()
    assert body["shown"] == 6 and body["store"] == "local" and len(body["categories"]) > 6


def test_the_admin_can_limit_and_hide_categories(client):
    first = client.get("/api/categories").get_json()["categories"][0]["name"]
    client.put("/api/admin/settings", json={"home_categories_max": "3", "home_categories_hidden": f"{first}, nothing-here"}, headers=ADMIN_HEADERS)
    body = client.get("/api/categories").get_json()
    assert body["shown"] == 3 and first not in [c["name"] for c in body["categories"]]
    assert client.put("/api/admin/settings", json={"home_categories_max": "99"}, headers=ADMIN_HEADERS).status_code == 400


def test_tapping_every_category_finds_that_categorys_products():
    """The home chips send 'Show me <category>'. Every one of them must return products, and the top result must be in it."""
    problems = []
    for cat in LocalStore().list_categories():
        r = chat_service.handle_query(f"Show me {cat['name']}", S)
        if not r.get("products") or r["products"][0]["category"] != cat["name"]:
            problems.append((cat["name"], [p["category"] for p in r.get("products", [])][:3]))
    assert not problems, problems


def test_fakestore_categories_are_counted_from_its_products():
    rows = FAKE_ROWS + [dict(FAKE_ROWS[0], id=20, category="women's clothing", title="Wrap Dress")]
    cats = FakeStore("https://fakestoreapi.com", http=FakeHttp(rows)).list_categories()
    assert {c["name"]: (c["count"], c["group"]) for c in cats} == {"men's clothing": (2, "Men"), "jewelery": (1, "More"), "women's clothing": (1, "Women")}


def test_a_fakestore_category_search_does_not_mix_mens_and_womens():
    rows = [dict(FAKE_ROWS[0], id=1, title="Slim Shirt", category="men's clothing"), dict(FAKE_ROWS[0], id=2, title="Wrap Dress", category="women's clothing")]
    store = FakeStore("https://fakestoreapi.com", http=FakeHttp(rows))
    assert [c["id"] for c in store.search_products(S, "Show me men's clothing")["products"]][:1] == [1]
    assert [c["id"] for c in store.search_products(S, "Show me women's clothing")["products"]][:1] == [2]


def test_woocommerce_categories_skip_empty_ones_and_decode_names():
    store = woo([{"name": "Saris &amp; Lehengas", "count": 4}, {"name": "Empty", "count": 0}])
    assert store.list_categories() == [{"name": "Saris & Lehengas", "count": 4, "group": "More"}]


def test_a_store_that_cannot_list_categories_gives_an_empty_home_list(client, monkeypatch):
    class NoCategories:
        name, capabilities = "bare", frozenset()

    monkeypatch.setattr("zaldi.services.categories.get_connector", lambda: NoCategories())
    assert client.get("/api/categories").get_json()["categories"] == []
