"""SQLite -> Postgres migration. It needs a real Postgres, so it only runs when ZALDI_TEST_DATABASE_URL is set."""
import os
import sqlite3

import pytest

from zaldi import config, stores
from zaldi.db import connect, init_db, migrate, pg
from zaldi.errors import ValidationError

pytestmark = pytest.mark.skipif(not os.getenv("ZALDI_TEST_DATABASE_URL"), reason="needs a Postgres database")


def build_sqlite(path):
    """A small SQLite installation made the old way: the real schema, a few rows, and ids that skip numbers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript((pg.SCHEMA_FILE).read_text(encoding="utf-8"))
    conn.execute("INSERT INTO products (id, product_code, product_name, category, price, stock_quantity) VALUES (5, 'K5', 'Kurta Five', 'Kurta', 999, 4)")
    conn.execute("INSERT INTO products (id, product_code, product_name, category, price, stock_quantity) VALUES (9, 'S9', 'Saree Nine', 'Saree', 4999, 2)")
    conn.execute("INSERT INTO policies (title, content) VALUES ('Returns', 'Returns within 7 days.')")
    conn.execute("INSERT INTO cart_items (session_id, product_id, quantity) VALUES ('sess-1', 5, 2)")
    conn.execute("INSERT INTO chat_logs (id, query, response, route) VALUES (3, 'hello', 'hi', 'chitchat')")
    conn.execute("INSERT INTO feedback (chat_id, rating) VALUES (3, 1)")
    conn.execute("INSERT INTO settings (key, value) VALUES ('brand_name', 'Old Brand')")
    conn.execute("INSERT INTO admin_users (email, password_hash, store, role) VALUES ('o@x.test', 'hash', 'default', 'owner')")
    conn.commit()
    conn.close()


def test_every_table_is_copied_ids_survive_and_new_rows_continue_after_them(temp_db):
    build_sqlite(config.DB_PATH)
    report = migrate.migrate_all()
    assert report["default"]["products"] == 2 and report["default"]["cart_items"] == 1 and report["default"]["admin_users"] == 1
    with connect() as conn:
        assert sorted(r["id"] for r in conn.execute("SELECT id FROM products")) == [5, 9]
        assert conn.execute("SELECT quantity FROM cart_items WHERE session_id = 'sess-1' AND product_id = 5").fetchone()["quantity"] == 2
        assert conn.execute("SELECT value FROM settings WHERE key = 'brand_name'").fetchone()["value"] == "Old Brand"
        assert conn.execute("SELECT rating FROM feedback WHERE chat_id = 3").fetchone()["rating"] == 1
        new = conn.execute("INSERT INTO products (product_code, product_name, price) VALUES ('N1', 'New', 1)").lastrowid
    assert new == 10  # the counter moved past the highest copied id, so nothing collides


def test_migrating_into_a_database_that_already_has_rows_is_refused_and_changes_nothing(temp_db):
    build_sqlite(config.DB_PATH)
    migrate.migrate_all()
    with pytest.raises(ValidationError, match="already has rows"):
        migrate.migrate_all()
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 2


def test_other_stores_are_copied_into_their_own_schemas(temp_db):
    build_sqlite(config.DB_PATH)
    shop = stores.db_path("shop-a")
    build_sqlite(shop)
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("INSERT INTO stores (slug, name) VALUES ('shop-a', 'Shop A')")
    sqlite3.connect(shop).execute("DELETE FROM products WHERE id = 9").connection.commit()
    report = migrate.migrate_all()
    assert report["shop-a"]["products"] == 1 and report["default"]["products"] == 2
    with stores.use("shop-a"), connect() as conn:
        assert [r["product_code"] for r in conn.execute("SELECT product_code FROM products")] == ["K5"]
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 2  # the default store is untouched


def test_it_refuses_to_run_without_a_postgres_url(temp_db, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", "")
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        migrate.migrate_all()
