"""First-run seeding from ``data/seed``: products.csv, policy.txt (``## `` sections) and quick_actions.csv."""
import csv
import sqlite3

from zaldi import config
from zaldi.db.content_repo import TABLES


def _insert_csv(conn: sqlite3.Connection, table: str, path) -> None:
    fields = TABLES[table].fields
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            conn.execute(
                f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join('?' * len(fields))})",
                [row.get(k) or None for k in fields],
            )


def _is_empty(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() is None


def seed_if_empty(conn: sqlite3.Connection) -> None:
    if _is_empty(conn, "products") and config.SEED_PRODUCTS_CSV.exists():
        _insert_csv(conn, "products", config.SEED_PRODUCTS_CSV)

    if _is_empty(conn, "policies") and config.SEED_POLICY_TXT.exists():
        for section in config.SEED_POLICY_TXT.read_text(encoding="utf-8").split("## ")[1:]:
            title, _, body = section.partition("\n")
            conn.execute("INSERT INTO policies (title, content) VALUES (?, ?)", (title.strip(), body.strip()))

    if _is_empty(conn, "quick_actions") and config.SEED_QUICK_ACTIONS_CSV.exists():
        _insert_csv(conn, "quick_actions", config.SEED_QUICK_ACTIONS_CSV)
