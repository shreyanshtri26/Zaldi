"""Bulk photo import: a folder of images named after product codes (``P001.jpg``, ``p014.png``) is stored and linked to those products.

Run it with ``python -m zaldi import-images <folder>``. Each file is validated by its own bytes (JPEG, PNG or WebP, up to 3 MB),
so a wrongly named or oversized file is reported and skipped, never linked.
"""
from pathlib import Path

from zaldi.api.uploads import save_image
from zaldi.db import connect
from zaldi.errors import ValidationError


def import_folder(folder: Path) -> dict:
    """Returns ``linked`` (product codes), ``unmatched`` (files with no product), ``rejected`` ((file, reason)) and
    ``without_photo`` (codes that still have no image afterwards)."""
    folder = Path(folder)
    if not folder.is_dir():
        raise ValidationError(f"{folder} is not a folder")
    linked, unmatched, rejected = [], [], []
    with connect() as conn:
        by_code = {r["product_code"].lower(): r["id"] for r in conn.execute("SELECT id, product_code FROM products")}
        for path in sorted(p for p in folder.iterdir() if p.is_file()):
            product_id = by_code.get(path.stem.lower())
            if product_id is None:
                unmatched.append(path.name)
                continue
            try:
                url = save_image(path.read_bytes())
            except ValidationError as exc:
                rejected.append((path.name, str(exc)))
                continue
            conn.execute("UPDATE products SET image_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (url, product_id))
            linked.append(path.stem.upper())
        without = [r["product_code"] for r in conn.execute("SELECT product_code FROM products WHERE image_url IS NULL OR image_url = '' ORDER BY id")]
    return {"linked": linked, "unmatched": unmatched, "rejected": rejected, "without_photo": without}
