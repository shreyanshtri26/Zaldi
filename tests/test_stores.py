"""Several stores on one server: each has its own data, a request is routed by its X-Store header, and worker threads keep the store."""
import pytest
from langchain_core.messages import AIMessage

from tests.helpers import ADMIN_HEADERS
from tests.test_agent_loop import call, scripted
from zaldi import stores
from zaldi.agent.loop import run_agent
from zaldi.connectors import get_connector
from zaldi.connectors.local import LocalStore
from zaldi.db import connect, init_db
from zaldi.errors import ValidationError

SID = {"X-Session-Id": "44444444-4444-4444-8444-444444444444"}


@pytest.fixture(autouse=True)
def env(temp_db):
    init_db()


def add_product(code, name, price=999):
    with connect() as conn:
        conn.execute("INSERT INTO products (product_code, product_name, category, material, size, color, brand, gender, stock_quantity, price, description) "
                     "VALUES (?, ?, 'Hat', 'Wool', 'M', 'Red', 'Acme', 'Unisex', 5, ?, 'A warm hat')", (code, name, price))


def test_a_new_store_starts_empty_and_does_not_touch_the_default_store():
    default_count = len(LocalStore().search_products("s", "kurta")["products"])
    stores.create_store("shop-one", "Shop One")
    with stores.use("shop-one"):
        assert LocalStore().search_products("s", "kurta")["products"] == []
        add_product("H1", "Winter Hat")
        assert [p["product_name"] for p in LocalStore().search_products("s", "hat")["products"]] == ["Winter Hat"]
    assert "Winter Hat" not in [p["product_name"] for p in LocalStore().search_products("s", "hat")["products"]]
    assert len(LocalStore().search_products("s", "kurta")["products"]) == default_count


def test_two_stores_keep_separate_products_carts_and_settings():
    stores.create_store("alpha", "Alpha")
    stores.create_store("beta", "Beta")
    for slug, code in (("alpha", "A1"), ("beta", "B1")):
        with stores.use(slug):
            add_product(code, f"{slug} hat")
    with stores.use("alpha"):
        pid = LocalStore().search_products("s1", "alpha hat")["products"][0]["id"]
        LocalStore().cart_add("s1", pid, 1)
        from zaldi.services import store_settings

        store_settings.update({"connector": "escuelajs"})
        assert get_connector().name == "escuelajs"
    with stores.use("beta"):
        assert [p["product_name"] for p in LocalStore().search_products("s1", "hat")["products"]] == ["beta hat"]
        assert LocalStore().cart_view("s1")["items"] == []  # the same session id in another store has its own, empty cart
        assert get_connector().name == "local"


def test_the_store_id_is_validated_and_the_default_cannot_be_removed():
    for bad in ("", "A", "ab", "Has Space", "x" * 40, "admin", "default", "api"):
        with pytest.raises(ValidationError):
            stores.create_store(bad, "Name")
    stores.create_store("taken", "One")
    with pytest.raises(ValidationError, match="already exists"):
        stores.create_store("taken", "Two")
    with pytest.raises(ValidationError):
        stores.delete_store("default")


def test_deleting_a_store_removes_its_registry_row_and_files():
    stores.create_store("gone", "Gone")
    folder = stores.root("gone")
    assert folder.exists()
    stores.delete_store("gone")
    assert not stores.exists("gone") and not folder.exists()


def test_the_header_routes_each_request_and_unknown_stores_are_refused(client):
    created = client.post("/api/admin/stores", json={"slug": "cafe", "name": "Cafe"}, headers=ADMIN_HEADERS)
    assert created.status_code == 201 and created.get_json()["status"] == "draft"
    with stores.use("cafe"):
        add_product("C1", "Cafe Mug")
    inside = client.get("/api/products?q=mug", headers={"X-Store": "cafe"}).get_json()
    outside = client.get("/api/products?q=mug").get_json()
    assert [p["product_name"] for p in inside] == ["Cafe Mug"] and "Cafe Mug" not in [p["product_name"] for p in outside]
    assert client.get("/api/products", headers={"X-Store": "nope"}).status_code == 400
    assert client.get("/api/products", headers={"X-Store": "../etc"}).status_code == 400
    assert stores.slug() == "default"  # a finished request leaves no store selected behind


def test_only_the_server_admin_can_manage_stores(client):
    assert client.get("/api/admin/stores").status_code == 401
    assert client.post("/api/admin/stores", json={"slug": "xyz", "name": "X"}).status_code == 401
    client.post("/api/admin/stores", json={"slug": "live-shop", "name": "Live"}, headers=ADMIN_HEADERS)
    assert client.put("/api/admin/stores/live-shop", json={"status": "live"}, headers=ADMIN_HEADERS).get_json()["status"] == "live"
    assert client.put("/api/admin/stores/live-shop", json={"status": "weird"}, headers=ADMIN_HEADERS).status_code == 400
    listed = [s["slug"] for s in client.get("/api/admin/stores", headers=ADMIN_HEADERS).get_json()["stores"]]
    assert listed == ["default", "live-shop"]
    assert client.delete("/api/admin/stores/live-shop", headers=ADMIN_HEADERS).status_code == 204


def test_parallel_tool_calls_run_against_the_same_store_as_the_chat():
    stores.create_store("threads", "Threads")
    with stores.use("threads"):
        add_product("T1", "Thread Hat")
        two = AIMessage(content="", tool_calls=[{"name": "search_products", "args": {"query": "hat"}, "id": "a"},
                                                {"name": "search_policies", "args": {"query": "returns"}, "id": "b"}])
        result = run_agent("hats and returns", "sess", LocalStore(), scripted(two, AIMessage(content="Done.")))
    assert [p["product_name"] for p in result["products"]] == ["Thread Hat"]  # a worker thread that lost the store would see the default catalogue


def test_the_stream_endpoint_keeps_the_store_in_its_worker_thread(client, monkeypatch):
    from zaldi.services import chat_service

    stores.create_store("streamy", "Streamy")
    seen = {}

    def fake(message, sid, image, history, on_step=None):
        seen["store"] = stores.slug()
        return {"response": "ok", "type": "agent"}

    monkeypatch.setattr(chat_service, "handle_query", fake)
    client.post("/api/chat/stream", json={"message": "hi"}, headers={**SID, "X-Store": "streamy"}).get_data()
    assert seen["store"] == "streamy"
