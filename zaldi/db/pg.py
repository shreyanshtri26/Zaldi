"""Postgres backend (Neon). Used when ``DATABASE_URL`` is set; otherwise the app uses SQLite files.

The rest of the app was written against sqlite3's style (``conn.execute(sql, params)``, ``?`` placeholders, rows readable by name or
position, ``cursor.lastrowid``). This module keeps that style so no query had to be rewritten for Postgres:

* ``?`` becomes ``%s`` and ``LIKE`` becomes ``ILIKE`` (SQLite's LIKE ignores case, Postgres' does not);
* an ``INSERT`` into a table with an ``id`` column gets ``RETURNING id`` so ``lastrowid`` works;
* ``schema.sql`` (the single source of truth) is translated: ``INTEGER PRIMARY KEY AUTOINCREMENT`` becomes ``SERIAL``, ``REAL`` becomes
  ``DOUBLE PRECISION``; timestamps stay text so the JSON the API returns is the same on both databases.

One store is one Postgres schema (``<base>_s_<slug>``); the default store uses the base schema (``PG_SCHEMA``, ``public`` by default).
Connections come from a pool (a new TLS connection per query would be far too slow against a hosted database).
"""
import re
import threading
from contextlib import contextmanager
from pathlib import Path

from zaldi import config

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS vectors (
    id        BIGSERIAL PRIMARY KEY,
    kind      TEXT NOT NULL,
    content   TEXT NOT NULL,
    meta      TEXT NOT NULL,
    embedding vector NOT NULL
);
CREATE INDEX IF NOT EXISTS vectors_kind ON vectors (kind);
CREATE TABLE IF NOT EXISTS vector_meta (
    kind        TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL
);
"""

# Timestamps are text in both databases, in SQLite's format, so they sort and print the same everywhere.
NOW = "to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS')"
_pool = None
_pool_url = None
_lock = threading.Lock()


def enabled() -> bool:
    return bool(config.DATABASE_URL)


def schema_name(store: str) -> str:
    """The Postgres schema holding ``store``'s tables. Built only from validated slugs, so it is safe to put in SQL."""
    from zaldi import stores

    base = config.PG_SCHEMA
    return base if store == stores.DEFAULT else f"{base}_s_{store.replace('-', '_')}"


def _get_pool():
    global _pool, _pool_url
    with _lock:
        if _pool is None or _pool_url != config.DATABASE_URL:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            if _pool is not None:
                _pool.close()
            _pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=int(config.PG_POOL_SIZE), open=True, timeout=30,
                                   kwargs={"row_factory": dict_row, "autocommit": False, "prepare_threshold": None})  # no server-side prepared statements: safe behind PgBouncer
            _pool_url = config.DATABASE_URL
    return _pool


def close_pool() -> None:
    global _pool, _pool_url
    with _lock:
        if _pool is not None:
            _pool.close()
        _pool, _pool_url = None, None


# --- translating sqlite-style SQL ----------------------------------------------------------------------------------------
def translate(sql: str) -> str:
    """``?`` -> ``%s`` and ``LIKE`` -> ``ILIKE`` outside string literals; a literal ``%`` is doubled so the driver leaves it alone."""
    out, quote = [], False
    for ch in sql:
        if ch == "'":
            quote = not quote
        if not quote and ch == "?":
            out.append("%s")
        elif ch == "%":
            out.append("%%")
        else:
            out.append(ch)
    text = re.sub(r"\bLIKE\b", "ILIKE", "".join(out))
    return re.sub(r"\bCURRENT_TIMESTAMP\b", NOW, text)


def translate_schema(sql: str) -> list[str]:
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY").replace("DEFAULT CURRENT_TIMESTAMP", f"DEFAULT ({NOW})")
    sql = re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql)
    return [s.strip() for s in sql.split(";") if s.strip()]


_ID_TABLES: set[str] | None = None


def id_tables() -> set[str]:
    """Tables with a serial ``id`` column: an INSERT into one of them returns the new id."""
    global _ID_TABLES
    if _ID_TABLES is None:
        text = SCHEMA_FILE.read_text(encoding="utf-8")
        _ID_TABLES = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+) \(\s*id\s+INTEGER PRIMARY KEY AUTOINCREMENT", text))
    return _ID_TABLES


class Row(dict):
    """A row readable by column name, by position (``row[0]``) and as a dict, like ``sqlite3.Row``."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class Cursor:
    def __init__(self, cur, lastrowid=None):
        self._cur, self.lastrowid = cur, lastrowid

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    def fetchone(self):
        row = self._cur.fetchone() if self._cur.description else None
        return Row(row) if row is not None else None

    def fetchall(self):
        return [Row(r) for r in self._cur.fetchall()] if self._cur.description else []

    def __iter__(self):
        return iter(self.fetchall())


class Connection:
    """A pooled connection with the sqlite3-style surface the app uses."""

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql: str, params=()) -> Cursor:
        sql = translate(sql)
        table = re.match(r"\s*INSERT\s+INTO\s+(\w+)", sql, re.I)
        returning = bool(table and table.group(1).lower() in id_tables() and "RETURNING" not in sql.upper())
        cur = self._raw.execute(sql + (" RETURNING id" if returning else ""), tuple(params))
        lastrowid = None
        if returning:
            row = cur.fetchone()
            lastrowid = row["id"] if row else None
        return Cursor(cur, lastrowid)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def executescript(self, script: str) -> None:
        for statement in translate_schema(script):
            self._raw.execute(statement)


@contextmanager
def connect(store: str | None = None):
    """A pooled connection pointed at the store's schema. Commits on success, rolls back on error, always returns to the pool."""
    from psycopg import errors  # noqa: F401  (imported here so SQLite-only installs never need psycopg)

    from zaldi import stores

    store = store or stores.slug()
    base = config.PG_SCHEMA
    path = f'"{schema_name(store)}", "{base}"' if store != stores.DEFAULT else f'"{base}"'
    with _get_pool().connection() as raw:
        raw.execute(f"SET search_path TO {path}, public")
        try:
            yield Connection(raw)
        except Exception:
            raw.rollback()
            raise
        else:
            raw.commit()


def ensure_schema(store: str) -> None:
    name = schema_name(store)
    with _get_pool().connection() as raw:
        raw.execute(f'CREATE SCHEMA IF NOT EXISTS "{name}"')
        raw.commit()


def drop_schema(store: str) -> None:
    with _get_pool().connection() as raw:
        raw.execute(f'DROP SCHEMA IF EXISTS "{schema_name(store)}" CASCADE')
        raw.commit()


_extension_ready = False


def init_schema(store: str) -> None:
    """Create the tables (and the pgvector tables) for one store, and add columns that older databases are missing.
    Everything goes in as one script, so a hosted database costs a couple of round trips, not forty."""
    global _extension_ready
    from zaldi.db.connection import MIGRATIONS

    name = schema_name(store)
    if not _extension_ready:
        with _get_pool().connection() as raw:
            raw.execute("CREATE EXTENSION IF NOT EXISTS vector")  # lives in public; the search path always includes it
            raw.commit()
        _extension_ready = True
    statements = [f'CREATE SCHEMA IF NOT EXISTS "{name}"', f'SET LOCAL search_path TO "{name}", "{config.PG_SCHEMA}", public',
                  f"SELECT pg_advisory_xact_lock({hash(name) & 0x7FFFFFFF})"]  # workers boot together: one builds, the rest wait
    statements += translate_schema(SCHEMA_FILE.read_text(encoding="utf-8")) + translate_schema(EXTRA_SCHEMA)
    statements += [f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS {c} {d.replace('REAL', 'DOUBLE PRECISION')}" for t, c, d in MIGRATIONS]
    with _get_pool().connection() as raw:
        raw.execute("; ".join(statements))
        raw.commit()


def integrity_error():
    from psycopg import errors

    return errors.IntegrityError
