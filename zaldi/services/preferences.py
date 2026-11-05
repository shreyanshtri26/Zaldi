"""Persistent shopper preferences. They are injected into every product search as default filters."""
from zaldi.db import connect
from zaldi.errors import ValidationError
from zaldi.search.extract import Filters

GENDERS = ("Men", "Women", "Boys", "Girls")
FIELDS = ("max_price", "brand", "exclude_brands", "size", "gender")


def get_preferences(session_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM preferences WHERE session_id = ?", (session_id,)).fetchone()
    return {k: row[k] for k in FIELDS} if row else dict.fromkeys(FIELDS)


def save_preferences(session_id: str, data: dict) -> dict:
    """Replace the saved preferences. Blank values clear a preference."""
    clean = {k: (str(data.get(k)).strip() if data.get(k) not in (None, "") else None) for k in FIELDS}
    if clean["max_price"] is not None:
        try:
            clean["max_price"] = int(clean["max_price"])
        except ValueError:
            raise ValidationError("max_price must be a whole number") from None
        if clean["max_price"] < 0:
            raise ValidationError("max_price must be >= 0")
    if clean["gender"] and clean["gender"] not in GENDERS:
        raise ValidationError(f"gender must be one of: {', '.join(GENDERS)}")
    with connect() as conn:
        conn.execute(
            "INSERT INTO preferences (session_id, max_price, brand, exclude_brands, size, gender) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET max_price=excluded.max_price, brand=excluded.brand, "
            "exclude_brands=excluded.exclude_brands, size=excluded.size, gender=excluded.gender, "
            "updated_at=CURRENT_TIMESTAMP",
            (session_id, *(clean[k] for k in FIELDS)))
    return get_preferences(session_id)


def preference_filters(session_id: str) -> Filters:
    p = get_preferences(session_id)
    genders = {"Men": ("Men", "Unisex"), "Women": ("Women", "Unisex")}.get(p["gender"], (p["gender"],) if p["gender"] else ())
    excluded = tuple(b.strip() for b in (p["exclude_brands"] or "").split(",") if b.strip())
    return Filters(brand=p["brand"], exclude_brands=excluded, size=p["size"], max_price=p["max_price"], genders=genders)
