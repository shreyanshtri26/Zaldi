"""Home-page categories: they come from the connected store, tapping each one finds its products, and the admin can trim them."""
import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from tests.helpers import ADMIN_HEADERS
from tests.test_connectors import ROWS, WOO_ROW, escuela, woo
from zaldi.connectors.local import LocalStore
from zaldi.db import connect, init_db
from zaldi.services import chat_service

S = "sess-cats-1"
GROUPS = {"Women", "Men", "Kids", "Everyone", "More"}


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
    assert body["shown"] == 24 and body["store"] == "local" and len(body["categories"]) == 18


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


def test_escuela_categories_feed_the_home_page():
    cats = escuela(ROWS).list_categories()
    assert [c["name"] for c in cats] == ["Shoes", "Electronics", "mylove"]  # count, then name; trimmed; empty "Misc" left out


def test_the_admin_can_hide_a_junk_category_from_an_open_sandbox_api(client, monkeypatch):
    monkeypatch.setattr("zaldi.services.categories.get_connector", lambda: escuela(ROWS))
    client.put("/api/admin/settings", json={"home_categories_hidden": "mylove"}, headers=ADMIN_HEADERS)
    names = [c["name"] for c in client.get("/api/categories").get_json()["categories"]]
    assert "mylove" not in names and "Shoes" in names


def test_woocommerce_categories_skip_empty_ones_and_decode_names():
    store = woo([{"name": "Saris &amp; Lehengas", "count": 4}, {"name": "Empty", "count": 0}])
    assert store.list_categories() == [{"name": "Saris & Lehengas", "count": 4, "group": "More", "image": None}]


def test_a_store_that_cannot_list_categories_gives_an_empty_home_list(client, monkeypatch):
    class NoCategories:
        name, capabilities = "bare", frozenset()

    monkeypatch.setattr("zaldi.services.categories.get_connector", lambda: NoCategories())
    assert client.get("/api/categories").get_json()["categories"] == []


def test_a_mixed_category_belongs_to_everyone_not_to_whichever_gender_came_first():
    groups = {c["name"]: c["group"] for c in LocalStore().list_categories()}
    assert groups["Footwear"] == "Everyone"     # men's, women's and unisex footwear
    assert groups["Kurta"] == "Everyone"        # one women's, one men's
    assert groups["Saree"] == "Women" and groups["Kurta Set"] == "Men" and groups["Kidswear"] == "Kids"


def test_a_category_uses_its_first_product_photo_and_has_none_when_nothing_has_one():
    assert all(c["image"] is None for c in LocalStore().list_categories())          # the built-in catalogue ships without photos
    with connect() as conn:
        conn.execute("UPDATE products SET image_url = '/uploads/first.png' WHERE id = (SELECT MIN(id) FROM products WHERE category = 'Saree')")
        conn.execute("UPDATE products SET image_url = '/uploads/later.png' WHERE id = (SELECT MAX(id) FROM products WHERE category = 'Saree')")
    images = {c["name"]: c["image"] for c in LocalStore().list_categories()}
    assert images["Saree"] == "/uploads/first.png" and images["Footwear"] is None


def test_escuela_and_woocommerce_categories_carry_a_real_picture_only():
    cats = {c["name"]: c["image"] for c in escuela(ROWS).list_categories()}
    assert cats["mylove"] == "https://i.imgur.com/a.jpeg" and cats["Shoes"] == "https://i.imgur.com/b.jpeg"   # Shoes skips its placeholder-only first item
    assert cats["Electronics"] is None
    woo_cats = woo([{"name": "Sarees", "count": 3, "image": {"src": "https://shop.example/s.jpg"}}, {"name": "Odd", "count": 1, "image": {"src": "javascript:x"}}]).list_categories()
    assert {c["name"]: c["image"] for c in woo_cats} == {"Sarees": "https://shop.example/s.jpg", "Odd": None}
