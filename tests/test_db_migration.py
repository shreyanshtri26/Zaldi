import sqlite3

from zaldi import config
from zaldi.db import content_repo, init_db


def test_older_database_gains_image_url_and_keeps_its_rows(temp_db):
    # A database created before image_url existed.
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("""CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_code TEXT NOT NULL UNIQUE, product_name TEXT NOT NULL,
            category TEXT, material TEXT, size TEXT, color TEXT, brand TEXT, gender TEXT,
            stock_quantity INTEGER NOT NULL DEFAULT 0, price INTEGER NOT NULL, description TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("INSERT INTO products (product_code, product_name, price) VALUES ('OLD1', 'Old Kurta', 500)")

    init_db()  # migrates, then seeds the other (empty) tables

    rows = content_repo.list_rows("products")
    assert [r["product_code"] for r in rows] == ["OLD1"]  # not re-seeded over existing data
    assert rows[0]["image_url"] is None
    created = content_repo.create_row("products", {"product_code": "N1", "product_name": "New", "price": 1,
                                                   "image_url": "/img/a.png"})
    assert created["image_url"] == "/img/a.png"


def test_init_db_is_idempotent(temp_db):
    init_db()
    first = len(content_repo.list_rows("products"))
    init_db()
    assert len(content_repo.list_rows("products")) == first
    assert len(content_repo.list_rows("quick_actions")) == 4
