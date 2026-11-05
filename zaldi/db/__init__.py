"""Persistence layer (SQLite): connection, schema/seed, and repositories."""
from zaldi.db.connection import connect, init_db

__all__ = ["connect", "init_db"]
