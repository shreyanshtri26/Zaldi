"""The "Test" step of store setup: one checklist that tells the admin, in plain words, whether their store connection is usable.

Each check has a name, a pass/fail, what was found, and a fix to try when it fails. The overall result also names the *level* of help the
agent can give through this store (catalogue, cart or orders), so the admin knows what shoppers will be able to do.
"""
from zaldi.connectors.base import capability_level
from zaldi.errors import ValidationError

SAMPLE = 20


def _check(name: str, ok: bool, detail: str, fix: str = "", blocking: bool = True) -> dict:
    """``blocking`` checks decide whether the store can go live; the others are advice shown next to them."""
    return {"name": name, "ok": ok, "detail": detail, "fix": "" if ok else fix, "blocking": blocking}


def check(store) -> dict:
    """Run the checklist against a connector. Never raises: a store that cannot be reached is a failed check, not a crash."""
    checks: list[dict] = []
    products: list[dict] = []
    try:
        products = store.search_products("admin-test", "", limit=SAMPLE)["products"]
        checks.append(_check("Store answers", True, "The store responded."))
    except ValidationError as exc:
        checks.append(_check("Store answers", False, str(exc), "Check the address and keys, then try again."))
    except Exception:
        checks.append(_check("Store answers", False, "The store could not be reached.", "Check the address and keys, then try again."))
    n = len(products)
    checks.append(_check("Products found", n > 0, f"Found {n} product{'s' if n != 1 else ''} in the sample." if n else "No products came back.",
                         "Make sure the store has products and the search address or feed is right."))
    if products:
        bad_price = [p for p in products if not isinstance(p.get("price"), (int, float)) or p["price"] <= 0]
        checks.append(_check("Prices are valid", not bad_price, "Every product has a price." if not bad_price else f"{len(bad_price)} of {n} products have no usable price.",
                             "Map the price field correctly (the portal shows sample values)."))
        missing_image = [p for p in products if not p.get("image_url")]
        checks.append(_check("Pictures present", len(missing_image) <= n // 2, f"{n - len(missing_image)} of {n} products have a picture.",
                             "Map the image field, or upload photos. Cards fall back to a fabric tile without one.", blocking=False))
        external = [p for p in products if p.get("catalogue_only")]
        no_link = [p for p in external if not p.get("buy_url")]
        if external:
            checks.append(_check("Buy links work", not no_link, "Every product has a link to buy it." if not no_link else f"{len(no_link)} of {len(external)} products have no safe link.",
                                 "Map the product link field; shoppers need it to buy.", blocking=False))
    extra = getattr(store, "problems", None)
    if extra:
        checks.append(_check("Pages read", False, f"{len(extra)} link(s) had problems: {extra[0]}", "Open the link in a browser; the page must show a product with a price.", blocking=False))
    skipped = getattr(store, "skipped_rows", 0) if products else 0
    if skipped:
        checks.append(_check("Rows usable", False, f"{skipped} feed row(s) were skipped (no name, id or price).", "Fix those rows in the feed or map the right columns.", blocking=False))
    level = capability_level(getattr(store, "capabilities", frozenset()))
    ok = all(c["ok"] for c in checks if c["blocking"])
    return {"ok": ok, "store": store.name, "level": level, "found": n, "sample": products[0]["product_name"] if products else None, "checks": checks}
