"""CRUD for the editable CMS content: products, policies and quick actions."""
import shutil
import sqlite3
from dataclasses import dataclass, field

from zaldi import stores
from zaldi.db.connection import connect
from zaldi.errors import ValidationError

Row = dict

# Icons the frontend can draw for quick-action cards.
ICON_NAMES = ("box", "grid", "doc", "shield", "chat", "search", "clock", "bot")


@dataclass(frozen=True)
class TableSpec:
    fields: tuple[str, ...]  # writable columns
    required: tuple[str, ...]  # must be present and non-empty on create
    search: tuple[str, ...]  # columns matched by the ``q`` filter
    order: str = "id"  # ORDER BY clause
    integers: tuple[str, ...] = ()  # columns coerced to non-negative ints
    choices: dict = field(default_factory=dict)  # column -> allowed values
    urls: tuple[str, ...] = ()  # columns that must be http(s) or root-relative URLs


TABLES: dict[str, TableSpec] = {
    "products": TableSpec(
        fields=("product_code", "product_name", "category", "material", "size", "color",
                "brand", "gender", "stock_quantity", "price", "description", "image_url"),
        required=("product_code", "product_name", "price"),
        search=("product_name", "description", "brand", "color"),
        integers=("price", "stock_quantity"),
        urls=("image_url",),
    ),
    "policies": TableSpec(
        fields=("title", "content"),
        required=("title", "content"),
        search=("title", "content"),
    ),
    "quick_actions": TableSpec(
        fields=("title", "subtitle", "message", "icon", "position", "active"),
        required=("title", "message"),
        search=("title", "subtitle", "message"),
        order="position, id",
        integers=("position", "active"),
        choices={"icon": ICON_NAMES, "active": (0, 1)},
    ),
}


def _spec(table: str) -> TableSpec:
    """Table names are interpolated into SQL, so only known tables may pass."""
    try:
        return TABLES[table]
    except KeyError:
        raise ValueError(f"unknown table: {table}") from None


def _clean(spec: TableSpec, data: dict, partial: bool) -> dict:
    row = {k: data[k] for k in spec.fields if k in data}
    if not partial:
        missing = [k for k in spec.required if row.get(k) in (None, "")]
        if missing:
            raise ValidationError(f"missing required field(s): {', '.join(missing)}")
    for key in spec.integers:
        if key in row:
            try:
                row[key] = int(row[key])
            except (TypeError, ValueError):
                raise ValidationError(f"{key} must be an integer") from None
            if row[key] < 0:
                raise ValidationError(f"{key} must be >= 0")
    for key, allowed in spec.choices.items():
        if key in row and row[key] not in allowed:
            raise ValidationError(f"{key} must be one of: {', '.join(map(str, allowed))}")
    for key in spec.urls:
        value = (row.get(key) or "").strip()
        if value and not value.startswith(("http://", "https://", "/")):
            raise ValidationError(f"{key} must start with http://, https:// or /")
        if key in row:
            row[key] = value or None
    return row


def list_rows(table: str, q: str = "", category: str = "", only_active: bool = False) -> list[Row]:
    spec = _spec(table)
    where, args = [], []
    if q:
        where.append("(" + " OR ".join(f"{c} LIKE ?" for c in spec.search) + ")")
        args += [f"%{q}%"] * len(spec.search)
    if category and table == "products":
        where.append("category = ? COLLATE NOCASE")
        args.append(category)
    if only_active and "active" in spec.fields:
        where.append("active = 1")
    sql = f"SELECT * FROM {table}" + (" WHERE " + " AND ".join(where) if where else "") + f" ORDER BY {spec.order}"
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def get_row(table: str, row_id: int) -> Row | None:
    _spec(table)
    with connect() as conn:
        found = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    return dict(found) if found else None


def create_row(table: str, data: dict) -> Row:
    row = _clean(_spec(table), data, partial=False)
    with connect() as conn:
        try:
            cursor = conn.execute(
                f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join('?' * len(row))})", list(row.values()))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(str(exc)) from exc
    _after_write(table)
    return get_row(table, cursor.lastrowid)


def update_row(table: str, row_id: int, data: dict) -> Row | None:
    row = _clean(_spec(table), data, partial=True)
    current = get_row(table, row_id)
    if current is None or not row:
        return current
    with connect() as conn:
        try:
            conn.execute(
                f"UPDATE {table} SET {','.join(k + '=?' for k in row)}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                [*row.values(), row_id])
        except sqlite3.IntegrityError as exc:
            raise ValidationError(str(exc)) from exc
    _after_write(table)
    return get_row(table, row_id)


def delete_row(table: str, row_id: int) -> bool:
    _spec(table)
    with connect() as conn:
        deleted = conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,)).rowcount > 0
    if deleted:
        _after_write(table)
    return deleted


def _after_write(table: str) -> None:
    """Policy text feeds the FAISS index: drop it so the next search rebuilds from the database."""
    if table == "policies":
        shutil.rmtree(stores.policy_index_dir(), ignore_errors=True)
        from zaldi.connectors.local import _policies

        _policies.cache_clear()  # and the five-minute answer cache, so an edit shows at once
