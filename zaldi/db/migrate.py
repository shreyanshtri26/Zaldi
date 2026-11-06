"""Copy a SQLite installation into Postgres: ``python -m zaldi migrate`` (needs ``DATABASE_URL``).

Every store is copied: the default store from ``config.DB_PATH`` (with the store registry and owner accounts) and each registered store
from its own folder. Rows keep their ids, so carts, orders and chat feedback still point at the right things; serial counters are moved
past the highest copied id. Search vectors are not copied: they are rebuilt from the data on the first search. The target tables must be
empty, so running it twice cannot duplicate anything. The SQLite files are only read, never changed.
"""
import sqlite3

from zaldi import stores
from zaldi.db import connect, init_db, pg
from zaldi.errors import ValidationError

# Parents before children, so every foreign key finds its row.
TABLES = ("products", "policies", "quick_actions", "settings", "prompts", "preferences", "session_state", "cart_items", "orders",
          "returns", "chat_logs", "feedback", "audit_log", "agents", "agent_runs", "approvals")
REGISTRY_TABLES = ("stores", "admin_users")  # live only in the default store's database
BATCH = 200


def _sqlite_rows(path, table: str) -> tuple[list[str], list[tuple]]:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            return [], []
        cur = conn.execute(f"SELECT * FROM {table}")
        return [d[0] for d in cur.description], cur.fetchall()
    finally:
        conn.close()


def _target_columns(conn, table: str) -> set[str]:
    return {r["column_name"] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = ?", (table,))}


def _copy_table(conn, path, table: str) -> int:
    columns, rows = _sqlite_rows(path, table)
    if not rows:
        return 0
    keep = [i for i, c in enumerate(columns) if c in _target_columns(conn, table)]  # a column the target lacks is dropped, not fatal
    names = [columns[i] for i in keep]
    if conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
        raise ValidationError(f"the Postgres table {table} already has rows; migrate into an empty database")
    one = "(" + ",".join("?" * len(names)) + ")"
    for start in range(0, len(rows), BATCH):
        chunk = rows[start:start + BATCH]
        conn.execute(f"INSERT INTO {table} ({','.join(names)}) VALUES {','.join([one] * len(chunk))}",
                     [row[i] for row in chunk for i in keep])
    if "id" in names and table in pg.id_tables():
        conn.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT MAX(id) FROM {table}))")
    return len(rows)


def migrate_store(store: str) -> dict[str, int]:
    """Copy one store's SQLite data into its Postgres schema. Returns rows copied per table."""
    path = stores.db_path(store)
    if not path.exists():
        return {}
    copied: dict[str, int] = {}
    with stores.use(store):
        init_db(seed=False)  # create the empty tables; nothing is seeded over the copy
        with connect() as conn:
            for table in TABLES + (REGISTRY_TABLES if store == stores.DEFAULT else ()):
                n = _copy_table(conn, path, table)
                if n:
                    copied[table] = n
    return copied


def _wipe() -> None:
    """Empty the Postgres target: drop every other store's schema and clear the default store's tables (the schema itself stays)."""
    with stores.use(stores.DEFAULT):
        init_db(seed=False)  # make sure the tables exist, so there is something to clear
        with connect() as conn:
            for row in conn.execute("SELECT slug FROM stores").fetchall():
                pg.drop_schema(row["slug"])
            conn.execute("TRUNCATE " + ", ".join(TABLES + REGISTRY_TABLES + ("vectors", "vector_meta")) + " RESTART IDENTITY CASCADE")


def migrate_all(replace: bool = False) -> dict[str, dict[str, int]]:
    """Copy every store. ``replace`` first erases whatever is in the Postgres target (the caller must have asked for that explicitly)."""
    if not pg.enabled():
        raise ValidationError("set DATABASE_URL to the Postgres database first")
    if replace:
        _wipe()
    report = {stores.DEFAULT: migrate_store(stores.DEFAULT)}  # first: it carries the registry that lists the other stores
    for row in stores.list_stores():
        if row["slug"] != stores.DEFAULT:
            report[row["slug"]] = migrate_store(row["slug"])
    return report
