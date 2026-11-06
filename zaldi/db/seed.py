"""First-run seeding from ``data/seed``: products.csv, policy.txt (``## `` sections) and quick_actions.csv."""
import csv

from zaldi import config
from zaldi.db.content_repo import TABLES


def _insert_rows(conn, table: str, fields, rows: list[list]) -> None:
    """One INSERT with many rows: one round trip, which matters on a hosted database."""
    if rows:
        one = "(" + ",".join("?" * len(fields)) + ")"
        conn.execute(f"INSERT INTO {table} ({','.join(fields)}) VALUES {','.join([one] * len(rows))}", [v for row in rows for v in row])


def _insert_csv(conn, table: str, path) -> None:
    fields = TABLES[table].fields
    with open(path, encoding="utf-8-sig", newline="") as f:
        _insert_rows(conn, table, fields, [[row.get(k) or None for k in fields] for row in csv.DictReader(f)])


def _is_empty(conn, table: str) -> bool:
    return conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() is None


def seed_if_empty(conn) -> None:
    if _is_empty(conn, "products") and config.SEED_PRODUCTS_CSV.exists():
        _insert_csv(conn, "products", config.SEED_PRODUCTS_CSV)

    if _is_empty(conn, "policies") and config.SEED_POLICY_TXT.exists():
        sections = [section.partition("\n") for section in config.SEED_POLICY_TXT.read_text(encoding="utf-8").split("## ")[1:]]
        _insert_rows(conn, "policies", ("title", "content"), [[title.strip(), body.strip()] for title, _, body in sections])

    if _is_empty(conn, "quick_actions") and config.SEED_QUICK_ACTIONS_CSV.exists():
        _insert_csv(conn, "quick_actions", config.SEED_QUICK_ACTIONS_CSV)
