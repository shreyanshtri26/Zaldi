import os
import uuid

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
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "ADMIN_TOKEN", ADMIN_TOKEN)
    # SQLite by default. With ZALDI_TEST_DATABASE_URL set, the same tests run on Postgres, each in its own throwaway schema.
    test_pg = os.getenv("ZALDI_TEST_DATABASE_URL", "")
    monkeypatch.setattr(config, "DATABASE_URL", test_pg)
    schema = f"t_{uuid.uuid4().hex[:10]}"
    monkeypatch.setattr(config, "PG_SCHEMA", schema)
    monkeypatch.setattr(config, "RATE_LIMIT_CHAT", 0)  # limits are tested explicitly
    monkeypatch.setattr(config, "RATE_LIMIT_LOGIN", 0)
    from zaldi.connectors.local import _policies

    _policies.cache_clear()  # cached answers belong to the previous test's database
    yield tmp_path
    if test_pg:
        import psycopg  # own connection: a test may have changed config.DATABASE_URL, so the app's pool is not safe to use here

        with psycopg.connect(test_pg, autocommit=True) as raw:  # the default store's schema and every store schema made from it
            names = [r[0] for r in raw.execute("SELECT nspname FROM pg_namespace WHERE nspname LIKE %s", (schema + "%",)).fetchall()]
            for name in names:
                raw.execute(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')


@pytest.fixture
def client(temp_db):
    app = create_app()
    app.testing = True
    return app.test_client()
