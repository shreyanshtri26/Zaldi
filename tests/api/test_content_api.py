import pytest

from tests.helpers import ADMIN_HEADERS


def test_seed_data_is_loaded(client):
    products = client.get("/api/products").get_json()
    assert len(products) >= 30
    assert any(p["category"] == "Saree" for p in products)
    assert all(p["price"] > 0 for p in products)  # INR prices
    assert len(client.get("/api/policies").get_json()) >= 8


def test_search_and_category_filter(client):
    sarees = client.get("/api/products?category=saree").get_json()
    assert sarees and all(p["category"] == "Saree" for p in sarees)
    assert client.get("/api/products?q=banarasi").get_json()


def test_writes_require_admin_token(client):
    assert client.post("/api/products", json={}).status_code == 401
    assert client.post("/api/products", json={}, headers={"X-Admin-Token": "wrong"}).status_code == 401


def test_writes_disabled_without_configured_token(client, monkeypatch):
    from zaldi import config
    monkeypatch.setattr(config, "ADMIN_TOKEN", None)
    assert client.post("/api/products", json={}, headers=ADMIN_HEADERS).status_code == 503


def test_product_crud_roundtrip(client):
    new = {"product_code": "T1", "product_name": "Test Kurta", "price": "999", "stock_quantity": 5}
    created = client.post("/api/products", json=new, headers=ADMIN_HEADERS)
    assert created.status_code == 201
    product_id = created.get_json()["id"]

    updated = client.put(f"/api/products/{product_id}", json={"price": 1099}, headers=ADMIN_HEADERS)
    assert updated.get_json()["price"] == 1099

    assert client.delete(f"/api/products/{product_id}", headers=ADMIN_HEADERS).status_code == 204
    assert client.get(f"/api/products/{product_id}").status_code == 404


@pytest.mark.parametrize("payload", [
    {"product_name": "x", "price": 1},                                   # missing product_code
    {"product_code": "T2", "product_name": "x", "price": -5},             # negative price
    {"product_code": "T2", "product_name": "x", "price": "abc"},          # non-numeric price
    {"product_code": "P001", "product_name": "dup", "price": 1},          # duplicate product_code
])
def test_invalid_product_is_rejected(client, payload):
    assert client.post("/api/products", json=payload, headers=ADMIN_HEADERS).status_code == 400


def test_editing_a_policy_invalidates_the_search_index(client, temp_db):
    index_dir = temp_db / "policy_index"
    index_dir.mkdir()
    (index_dir / "index.faiss").write_text("stale")
    policy_id = client.get("/api/policies").get_json()[0]["id"]
    client.put(f"/api/policies/{policy_id}", json={"content": "New content"}, headers=ADMIN_HEADERS)
    assert not index_dir.exists()


def test_admin_stats_require_token(client):
    assert client.get("/api/admin/stats").status_code == 401
    stats = client.get("/api/admin/stats", headers=ADMIN_HEADERS).get_json()
    assert stats["products"] >= 30 and "recent_chats" in stats


def test_unknown_api_path_is_json_404(client):
    response = client.get("/api/nope")
    assert response.status_code == 404 and response.get_json() == {"error": "not found"}


def test_chat_requires_a_message(client):
    assert client.post("/api/chat", json={}).status_code == 400
