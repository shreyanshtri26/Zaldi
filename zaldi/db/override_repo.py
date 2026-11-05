"""Key/value overrides for site settings and assistant prompts.

A missing row means "use the built-in default", so deleting a row resets it.
"""
from zaldi.db.connection import connect

_KEY_COLUMN = {"settings": "key", "prompts": "name"}


def _column(table: str) -> str:
    try:
        return _KEY_COLUMN[table]
    except KeyError:
        raise ValueError(f"unknown override table: {table}") from None


def get_overrides(table: str) -> dict[str, str]:
    column = _column(table)
    with connect() as conn:
        return {r[column]: r["content" if table == "prompts" else "value"]
                for r in conn.execute(f"SELECT * FROM {table}")}


def get_override(table: str, key: str) -> str | None:
    return get_overrides(table).get(key)


def set_override(table: str, key: str, value: str) -> None:
    column, value_column = _column(table), "content" if table == "prompts" else "value"
    with connect() as conn:
        conn.execute(
            f"INSERT INTO {table} ({column}, {value_column}) VALUES (?, ?) "
            f"ON CONFLICT({column}) DO UPDATE SET {value_column}=excluded.{value_column}, updated_at=CURRENT_TIMESTAMP",
            (key, value))


def delete_override(table: str, key: str) -> None:
    with connect() as conn:
        conn.execute(f"DELETE FROM {table} WHERE {_column(table)} = ?", (key,))
