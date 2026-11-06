import sqlite3

from zaldi import config, stores
from zaldi.db import content_repo, init_db, pg


def test_older_database_gains_image_url_and_keeps_its_rows(temp_db):
    # A database created before image_url existed.
    if pg.enabled():
        pg.ensure_schema(stores.DEFAULT)
        with pg.connect() as conn:
            conn.execute("""CREATE TABLE products (
                id SERIAL PRIMARY KEY, product_code TEXT NOT NULL UNIQUE, product_name TEXT NOT NULL,
                category TEXT, material TEXT, size TEXT, color TEXT, brand TEXT, gender TEXT,
                stock_quantity INTEGER NOT NULL DEFAULT 0, price INTEGER NOT NULL, description TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            conn.execute("INSERT INTO products (product_code, product_name, price) VALUES ('OLD1', 'Old Kurta', 500)")
    else:
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
    assert len(content_repo.list_rows("quick_actions")) == 2  # Payment, Returns (categories come from the store)


def test_concurrent_first_boots_seed_once(tmp_path):
    """Several gunicorn workers booting on an empty database must not collide on the seed rows.

    Real processes are needed: threads in one process do not reproduce the race. (Without the write lock in
    init_db this fails roughly every other run, so a pass is strong evidence rather than proof.)
    """
    import os
    import subprocess
    import sys

    env = os.environ | {"DATA_DIR": str(tmp_path), "EMBEDDING_PROVIDER": "local"}
    cmd = [sys.executable, "-c", "from zaldi.db import init_db; init_db()"]
    procs = [subprocess.Popen(cmd, env=env, stderr=subprocess.PIPE, text=True) for _ in range(8)]
    errors = [err for p in procs for err in [p.communicate()[1]] if p.returncode != 0]
    assert not errors, errors
