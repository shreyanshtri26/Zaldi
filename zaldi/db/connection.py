"""SQLite connection handling and first-run initialisation."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from zaldi import config

SCHEMA_FILE = Path(__file__).with_name("schema.sql")

# Columns added after the first release: (table, column, definition).
MIGRATIONS = [("products", "image_url", "TEXT"), ("chat_logs", "steps", "TEXT")]


@contextmanager
def connect(readonly: bool = False) -> Iterator[sqlite3.Connection]:
    """Yield a connection that commits on success and always closes.

    (sqlite3's own ``with`` never closes the connection, which locks the file on Windows.)
    """
    if readonly:
        conn = sqlite3.connect(f"file:{config.DB_PATH.as_posix()}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(config.DB_PATH, timeout=30)  # several gunicorn workers share this file
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns that older databases are missing (CREATE TABLE IF NOT EXISTS never alters a table)."""
    for table, column, definition in MIGRATIONS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    """Create tables, migrate older databases, and seed from ``data/seed`` when empty."""
    from zaldi.db.seed import seed_if_empty

    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        # Workers boot together: the write lock makes the second one wait, then find the tables already seeded.
        conn.execute("BEGIN IMMEDIATE")
        _migrate(conn)
        seed_if_empty(conn)
