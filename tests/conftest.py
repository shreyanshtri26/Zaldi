import pytest

from tests.helpers import ADMIN_TOKEN
from zaldi import config, create_app


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the app at a throwaway data directory (seeded on first use)."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "POLICY_INDEX_DIR", tmp_path / "policy_index")
    monkeypatch.setattr(config, "PRODUCT_INDEX_DIR", tmp_path / "product_index")
    monkeypatch.setattr(config, "EMBEDDING_PROVIDER", "local")  # offline, deterministic
    monkeypatch.setattr(config, "ROUTER_CACHE_DIR", tmp_path / "router_cache")
    monkeypatch.setattr(config, "ADMIN_TOKEN", ADMIN_TOKEN)
    return tmp_path


@pytest.fixture
def client(temp_db):
    app = create_app()
    app.testing = True
    return app.test_client()
