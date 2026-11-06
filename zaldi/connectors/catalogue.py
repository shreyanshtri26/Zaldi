"""Shared pieces for catalogue-only connectors (feed, REST, link pages, Amazon, Flipkart): read a store's products, turn each into the
card format the page and the agent already understand, and search/filter/sort them.

These stores give search and a link, not a cart: the shopper buys on the store itself, so every card carries ``buy_url`` and
``catalogue_only``. ``source`` names where the product came from, shown on the card ("from Amazon").
"""
import re

from zaldi.connectors.base import SEARCH, safe_url, sort_intent

DESCRIPTION_LIMIT = 240
STOPWORDS = {"show", "find", "give", "want", "need", "looking", "some", "the", "and", "for", "with", "under", "below", "above",
             "over", "than", "less", "more", "me", "please", "any", "can", "you", "have", "has", "best", "good", "cheap", "cheaper",
             "cheapest", "compare", "between", "which", "one", "what", "are", "your", "all", "top", "rated", "most", "expensive",
             "lowest", "price", "highest", "popular", "premium"}


def dig(obj, path: str, default=None):
    """Follow ``a.b.0.c`` through dicts and lists; anything missing gives ``default``."""
    for part in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        else:
            return default
        if obj is None:
            return default
    return obj


def dig_any(obj, *paths: str, default=None):
    """The first path that exists (stores spell the same field differently: ``itemInfo.title`` or ``ItemInfo.Title``)."""
    for path in paths:
        value = dig(obj, path)
        if value not in (None, "", [], {}):
            return value
    return default


def money(value) -> float | None:
    """A number from ``1299``, ``"1,299.00"``, ``"Rs. 1,299"`` or ``"1299.00 INR"``; ``None`` when there is no price."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(value or ""))
    if not match:
        return None
    number = float(match.group(0).replace(",", ""))
    return number if number > 0 else None


def clean_text(value, limit: int = DESCRIPTION_LIMIT) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", str(value or "")).split())[:limit]


def make_card(pid, name, price, currency="INR", *, category="", brand="", image=None, url=None, description="", rating=None,
              rating_count=None, in_stock=None, source="", color="", size="", material="") -> dict | None:
    """One product in the standard card format, or ``None`` when it has no name, id or usable price (such rows are never shown)."""
    price = money(price)
    name = clean_text(name, 200)
    if not name or price is None or pid in (None, ""):
        return None
    return {"id": pid, "product_name": name, "brand": clean_text(brand, 80), "category": clean_text(category, 80), "color": color, "size": size,
            "material": material, "price": price, "currency": (currency or "INR").upper()[:3],
            "stock_quantity": 0 if in_stock is False else None,  # None = the store did not say, which is not "in stock"
            "image_url": safe_url(image), "buy_url": safe_url(url), "description": clean_text(description),
            "rating": float(rating) if isinstance(rating, (int, float)) and not isinstance(rating, bool) and 0 < rating <= 5 else None,
            "rating_count": int(rating_count) if isinstance(rating_count, (int, float)) and not isinstance(rating_count, bool) and rating_count > 0 else None,
            "catalogue_only": True, "source": source}


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _words(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9']+", (text or "").lower())}


def rank(cards: list[dict], query: str, filters: dict | None, limit: int) -> list[dict]:
    """Filter by category and budget, score by words in the name, category, brand and description, and honour "cheapest" and so on."""
    filters = filters or {}
    sort = filters.get("sort") or sort_intent(query)
    category = (filters.get("category") or "").lower()
    low, high = filters.get("min_price"), filters.get("max_price")
    terms = [_stem(w) for w in re.findall(r"[a-z0-9']+", query.lower()) if w not in STOPWORDS and len(w) > 2 and not w.isdigit()]
    pool, scored = [], []
    for c in cards:
        if category and c["category"].lower() != category:
            continue
        if (low and c["price"] < low) or (high and c["price"] > high):
            continue
        title, cat, brand, about = _words(c["product_name"]), _words(c["category"]), _words(c["brand"]), _words(c["description"])
        score = sum(3 * (t in title) + 2 * (t in cat or t in brand) + (t in about) for t in terms)
        pool.append((score, c))
        if score or not terms:
            scored.append((score, c))
    if sort and not scored:
        scored = pool
    key = {"price_asc": lambda s: (s[1]["price"], str(s[1]["id"])), "price_desc": lambda s: (-s[1]["price"], str(s[1]["id"])),
           "rating": lambda s: (-(s[1]["rating"] or 0), -s[0], str(s[1]["id"]))}.get(sort) or (lambda s: (-s[0], str(s[1]["id"])))
    return [c for _, c in sorted(scored, key=key)[:limit]]


class CatalogueStore:
    """Base for connectors that can list their products in one go (feed, REST, link pages). Subclasses implement ``_cards()``."""

    capabilities = frozenset({SEARCH})
    name = "catalogue"

    def _cards(self) -> list[dict]:
        raise NotImplementedError

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        return {"products": rank(self._cards(), query or "", filters, limit), "relaxed": []}

    def get_product(self, product_id) -> dict | None:
        return next((c for c in self._cards() if str(c["id"]) == str(product_id)), None)

    def list_categories(self) -> list[dict]:
        counts: dict[str, int] = {}
        for c in self._cards():
            if c["category"]:
                counts[c["category"]] = counts.get(c["category"], 0) + 1
        return sorted(({"name": n, "count": k, "group": "More", "image": None} for n, k in counts.items()), key=lambda c: (-c["count"], c["name"]))
