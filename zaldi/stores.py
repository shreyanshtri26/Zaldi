"""Several stores on one server. Each store has its own database, search indexes and settings, so one store can never read
another's products, carts, orders, chats or keys.

The store for a request is chosen from its ``X-Store`` header (a slug) and held in a context variable. The ``default`` store is the
original database at ``config.DB_PATH``; every other store lives in ``<data dir>/stores/<slug>/``. The registry of stores is a
table in the default database.
"""
import contextvars
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

from zaldi import config
from zaldi.errors import ValidationError

DEFAULT = "default"
SLUG = re.compile(r"[a-z][a-z0-9-]{1,30}[a-z0-9]")
RESERVED = {DEFAULT, "admin", "api", "stores", "uploads", "store-sim", "assets", "widget"}
STATUSES = ("draft", "live")

current: contextvars.ContextVar[str] = contextvars.ContextVar("zaldi_store", default=DEFAULT)


def slug() -> str:
    return current.get()


def root(store: str | None = None) -> Path:
    """Folder holding a store's files. The default store keeps its original locations."""
    store = store or slug()
    return config.DB_PATH.parent if store == DEFAULT else config.DB_PATH.parent / "stores" / store


def db_path(store: str | None = None) -> Path:
    store = store or slug()
    return config.DB_PATH if store == DEFAULT else root(store) / "zaldi.db"


def policy_index_dir(store: str | None = None) -> Path:
    store = store or slug()
    return config.POLICY_INDEX_DIR if store == DEFAULT else root(store) / "policy_index"


def product_index_dir(store: str | None = None) -> Path:
    store = store or slug()
    return config.PRODUCT_INDEX_DIR if store == DEFAULT else root(store) / "product_index"


@contextmanager
def use(store: str):
    """Run a block against ``store``. Threads do not inherit this: use ``carry`` when handing work to one."""
    token = current.set(store)
    try:
        yield
    finally:
        current.reset(token)


def carry(fn):
    """Wrap ``fn`` so that, run in another thread, it works against the store of the thread that wrapped it."""
    store = slug()

    def run(*args, **kwargs):
        with use(store):
            return fn(*args, **kwargs)

    return run


# --- the registry (always in the default store's database) ---------------------------------------------------------------
def _registry():
    from zaldi.db.connection import connect

    return connect(store=DEFAULT)


def exists(store: str) -> bool:
    if store == DEFAULT:
        return True
    with _registry() as conn:
        return conn.execute("SELECT 1 FROM stores WHERE slug = ?", (store,)).fetchone() is not None


def list_stores() -> list[dict]:
    with _registry() as conn:
        rows = [dict(r) for r in conn.execute("SELECT slug, name, status, created_at FROM stores ORDER BY created_at, slug")]
    return [{"slug": DEFAULT, "name": "Default store", "status": "live", "created_at": None}] + rows


def get_store(store: str) -> dict | None:
    return next((s for s in list_stores() if s["slug"] == store), None)


def create_store(store: str, name: str) -> dict:
    """Make a new, empty store: its own database with the tables and no sample products."""
    from zaldi.db.connection import init_db

    store, name = (store or "").strip().lower(), " ".join((name or "").split())[:80]
    if not SLUG.fullmatch(store) or store in RESERVED:
        raise ValidationError("the store id must be 3-32 lowercase letters, digits or dashes, starting with a letter")
    if not name:
        raise ValidationError("a store name is required")
    if exists(store):
        raise ValidationError("a store with that id already exists")
    with _registry() as conn:
        conn.execute("INSERT INTO stores (slug, name) VALUES (?, ?)", (store, name))
    with use(store):
        init_db(seed=False)
    return get_store(store)


def set_status(store: str, status: str) -> dict:
    if status not in STATUSES:
        raise ValidationError("status must be draft or live")
    if store == DEFAULT or not exists(store):
        raise ValidationError("unknown store")
    with _registry() as conn:
        conn.execute("UPDATE stores SET status = ? WHERE slug = ?", (status, store))
    return get_store(store)


def delete_store(store: str) -> None:
    if store == DEFAULT or not exists(store):
        raise ValidationError("unknown store")
    with _registry() as conn:
        conn.execute("DELETE FROM stores WHERE slug = ?", (store,))
    shutil.rmtree(root(store), ignore_errors=True)
