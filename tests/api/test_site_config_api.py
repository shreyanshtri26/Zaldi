import pytest

from tests.helpers import ADMIN_HEADERS
from zaldi.services import site_config


def test_site_config_defaults_reproduce_the_original_ui(client):
    config = client.get("/api/site-config").get_json()
    assert config["settings"] == site_config.defaults()
    assert config["settings"]["welcome_greeting"] == "Hi there, Zaldi."
    assert config["settings"]["welcome_heading"] == "What's on *your mind*?"
    assert [a["title"] for a in config["quick_actions"]] == ["Payment", "Returns"]
    assert config["quick_actions"][0]["message"] == "Is COD available?"


def test_settings_override_and_reset(client):
    changed = client.put("/api/admin/settings", json={"brand_name": "Zaldi Silks"}, headers=ADMIN_HEADERS)
    assert changed.get_json()["settings"]["brand_name"] == "Zaldi Silks"
    assert client.get("/api/site-config").get_json()["settings"]["brand_name"] == "Zaldi Silks"

    reset = client.put("/api/admin/settings", json={"brand_name": "  "}, headers=ADMIN_HEADERS)  # empty = default
    assert reset.get_json()["settings"]["brand_name"] == "Zaldi"


@pytest.mark.parametrize("payload", [
    {"nope": "x"},                       # unknown key
    {"brand_name": 5},                   # not text
    {"brand_name": "x" * 500},           # too long
])
def test_invalid_settings_are_rejected(client, payload):
    assert client.put("/api/admin/settings", json=payload, headers=ADMIN_HEADERS).status_code == 400


def test_settings_endpoints_need_the_admin_token(client):
    assert client.get("/api/admin/settings").status_code == 401
    assert client.put("/api/admin/settings", json={"brand_name": "x"}).status_code == 401


def test_quick_actions_crud_order_and_visibility(client):
    created = client.post("/api/quick_actions", headers=ADMIN_HEADERS, json={
        "title": "Offers", "message": "Any offers today?", "icon": "clock", "position": 0})
    assert created.status_code == 201
    new_id = created.get_json()["id"]

    titles = [a["title"] for a in client.get("/api/site-config").get_json()["quick_actions"]]
    assert titles[0] == "Offers" and len(titles) == 5  # position 0 sorts first

    client.put(f"/api/quick_actions/{new_id}", json={"active": 0}, headers=ADMIN_HEADERS)
    assert "Offers" not in [a["title"] for a in client.get("/api/site-config").get_json()["quick_actions"]]
    assert client.delete(f"/api/quick_actions/{new_id}", headers=ADMIN_HEADERS).status_code == 204


@pytest.mark.parametrize("payload", [
    {"title": "x", "message": "y", "icon": "not-an-icon"},
    {"title": "x", "message": "y", "active": 2},
    {"title": "x"},                                   # message required
])
def test_invalid_quick_actions_are_rejected(client, payload):
    assert client.post("/api/quick_actions", json=payload, headers=ADMIN_HEADERS).status_code == 400


def test_product_image_url_is_validated(client):
    base = {"product_code": "IMG1", "product_name": "Img Kurta", "price": 100}
    ok = client.post("/api/products", json={**base, "image_url": "https://example.com/a.jpg"}, headers=ADMIN_HEADERS)
    assert ok.status_code == 201 and ok.get_json()["image_url"] == "https://example.com/a.jpg"
    bad = client.post("/api/products", json={**base, "product_code": "IMG2", "image_url": "javascript:alert(1)"},
                      headers=ADMIN_HEADERS)
    assert bad.status_code == 400
