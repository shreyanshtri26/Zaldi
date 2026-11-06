"""Admin store setup: choose the connector and enter its details without editing .env."""
import json

import pytest

from tests.helpers import ADMIN_HEADERS
from zaldi import config
from zaldi.connectors import get_connector
from zaldi.connectors.escuelajs import EscuelaStore

ROWS = [{"id": 1, "title": "Test Dress", "price": 20, "description": "A dress", "images": [], "category": {"name": "Clothes"}}]


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(config, "STORE_CONNECTOR", "local")
    get_connector.cache_clear()
    yield
    get_connector.cache_clear()


def put(client, **body):
    return client.put("/api/admin/store", json=body, headers=ADMIN_HEADERS)


def test_store_settings_need_the_admin_token(client):
    assert client.get("/api/admin/store").status_code == 401
    assert client.put("/api/admin/store", json={"connector": "escuelajs"}).status_code == 401
    assert client.post("/api/admin/store/test").status_code == 401


def test_choosing_a_connector_takes_effect_immediately(client):
    assert get_connector().name == "local"
    assert put(client, connector="escuelajs").get_json()["values"]["connector"] == "escuelajs"
    assert get_connector().name == "escuelajs"          # the cache was rebuilt, no restart needed


def test_secrets_are_write_only(client):
    out = put(client, connector="woocommerce", woocommerce_url="https://shop.example", woocommerce_key="ck_SECRETKEY", woocommerce_secret="cs_SECRETVALUE")
    body = json.dumps(out.get_json()) + json.dumps(client.get("/api/admin/store", headers=ADMIN_HEADERS).get_json())
    assert "SECRETKEY" not in body and "SECRETVALUE" not in body
    assert out.get_json()["secrets_set"]["woocommerce_key"] is True


def test_a_blank_secret_keeps_the_saved_one_and_a_blank_setting_resets(client):
    put(client, connector="woocommerce", woocommerce_url="https://shop.example", woocommerce_key="ck_1", woocommerce_secret="cs_1")
    again = put(client, woocommerce_key="", woocommerce_url="").get_json()
    assert again["secrets_set"]["woocommerce_key"] is True            # blank secret = unchanged
    assert again["values"]["woocommerce_url"] == ""                   # blank setting = back to the environment (empty here)


@pytest.mark.parametrize("payload", [
    {"connector": "magento"},                                          # not a known connector
    {"woocommerce_url": "http://insecure.example"},                    # https only
    {"shopify_domain": "evil.example.com"},                            # must be a myshopify.com domain
    {"nope": "x"}, {"connector": 5}, {"woocommerce_key": "k" * 500},
])
def test_invalid_store_settings_are_rejected(client, payload):
    assert put(client, **payload).status_code == 400


def test_reset_returns_to_the_environment(client):
    put(client, connector="escuelajs")
    out = client.delete("/api/admin/store", headers=ADMIN_HEADERS).get_json()
    assert out["values"]["connector"] == "local" and out["overridden"] == [] and get_connector().name == "local"


def test_connection_test_reports_success_without_leaking_anything(client, monkeypatch):
    monkeypatch.setattr(EscuelaStore, "_all", lambda self: ROWS)
    put(client, connector="escuelajs", escuelajs_url="https://api.escuelajs.co/api/v1")
    out = client.post("/api/admin/store/test", headers=ADMIN_HEADERS).get_json()
    assert (out["ok"], out["store"], out["found"], out["sample"], out["level"]) == (True, "escuelajs", 1, "Test Dress", "catalogue")
    assert {c["name"] for c in out["checks"]} >= {"Store answers", "Products found", "Prices are valid"}


def test_connection_test_explains_a_misconfigured_store_in_plain_words(client):
    put(client, connector="woocommerce")                               # no address or keys yet
    out = client.post("/api/admin/store/test", headers=ADMIN_HEADERS).get_json()
    assert out["ok"] is False and "https://" in out["message"]
