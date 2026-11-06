"""Fake Store API (https://fakestoreapi.com, source: github.com/keikaavousi/fake-store-api): a free demo catalogue, no key.

A good stand-in for "any other store": it proves the agent works against a catalogue it did not ship with. It uses the
documented read endpoints: ``/products`` (cached for ``TTL`` seconds, with ``/products/categories`` for the category list) and
``/products/category/{name}`` when a shopper names a category. The API has no free-text search and no stock counts, so text
matching is done here and availability is reported as unknown. Ratings come from each product's ``rating`` object. The write
endpoints (carts, users, login) are simulated by the API and never touched. Catalogue-only: no buy link, no cart tools.
"""
import re
import time
import urllib.parse

import requests

from zaldi.connectors.base import SEARCH, safe_url, sort_intent
from zaldi.errors import ValidationError

BASE_URL = "https://fakestoreapi.com"
TIMEOUT = 10
TTL = 600  # seconds a fetched list is reused, so repeated questions cost no request
DESCRIPTION_LIMIT = 240
STOPWORDS = {"show", "find", "give", "want", "need", "looking", "some", "the", "and", "for", "with", "under", "below", "above",
             "over", "than", "less", "more", "me", "please", "any", "can", "you", "have", "has", "best", "good", "cheap", "cheaper",
             "cheapest", "compare", "between", "which", "one", "what", "are", "your", "all", "top", "rated", "most", "expensive",
             "lowest", "price", "highest", "popular", "premium"}


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


class FakeStore:
    name = "fakestore"
    capabilities = frozenset({SEARCH})

    def __init__(self, base_url: str = BASE_URL, http=requests, clock=time.monotonic) -> None:
        self.base, self.http, self.clock = base_url.rstrip("/"), http, clock
        self._cache: dict[str, tuple[float, list]] = {}

    def _fetch(self, path: str) -> list:
        """GET a list endpoint, cached. A stale copy beats failing the shopper's question when the API is down."""
        hit = self._cache.get(path)
        if hit and self.clock() - hit[0] < TTL:
            return hit[1]
        try:
            response = self.http.get(f"{self.base}{path}", timeout=TIMEOUT)
            response.raise_for_status()
            rows = response.json()
        except Exception as exc:
            if hit:
                return hit[1]
            raise ValidationError("the store is not reachable right now") from exc
        self._cache[path] = (self.clock(), rows)
        return rows

    def _all(self) -> list[dict]:
        return self._fetch("/products")

    def _category_names(self) -> list[str]:
        try:
            names = self._fetch("/products/categories")
            if names and all(isinstance(n, str) for n in names):
                return names
        except ValidationError:
            pass
        return sorted({r.get("category") for r in self._all() if r.get("category")})

    def _in_category(self, category: str) -> list[dict]:
        """The documented ``/products/category/{name}`` listing; falls back to filtering the full list."""
        try:
            return self._fetch(f"/products/category/{urllib.parse.quote(category)}")
        except ValidationError:
            return [r for r in self._all() if r.get("category") == category]

    def _named_category(self, query: str) -> str | None:
        """A category the shopper named exactly. Whole-word match, longest name first, so "men's" never matches "women's"."""
        for name in sorted(self._category_names(), key=len, reverse=True):
            if re.search(r"(?<![a-z])" + re.escape(name.lower()) + r"(?![a-z])", query.lower()):
                return name
        return None

    @staticmethod
    def _card(row: dict) -> dict:
        rating = row.get("rating") or {}
        return {
            "id": row["id"], "product_name": row.get("title") or "", "brand": "", "category": row.get("category") or "", "color": "",
            "size": "", "material": "", "price": row.get("price") or 0, "currency": "USD",
            "stock_quantity": None,  # this API does not report stock: unknown, not "in stock"
            "image_url": safe_url(row.get("image")), "description": " ".join((row.get("description") or "").split())[:DESCRIPTION_LIMIT],
            "rating": rating.get("rate"), "rating_count": rating.get("count"), "catalogue_only": True,
        }

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        filters = filters or {}
        sort = filters.get("sort") or sort_intent(query)
        category = filters.get("category") or self._named_category(query)
        pool = self._in_category(category) if category else self._all()
        terms = [_stem(w) for w in re.findall(r"[a-z']+", query.lower()) if w not in STOPWORDS and len(w) > 2]
        low, high = filters.get("min_price"), filters.get("max_price")
        scored = []
        for row in pool:
            if (low and row["price"] < low) or (high and row["price"] > high):
                continue
            title, cat, about = (set(_stem(w) for w in re.findall(r"[a-z']+", row.get(k, "").lower())) for k in ("title", "category", "description"))
            score = sum(3 * (t in title) + 2 * (t in cat) + (t in about) for t in terms)  # whole words: "men's" must not match "women's"
            if score or not terms or category:  # a named category already narrowed the pool
                scored.append((score, row))
        rate = lambda r: (r.get("rating") or {}).get("rate") or 0  # noqa: E731
        orders = {"price_asc": lambda s: (s[1]["price"], s[1]["id"]), "price_desc": lambda s: (-s[1]["price"], s[1]["id"]),
                  "rating": lambda s: (-rate(s[1]), -((s[1].get("rating") or {}).get("count") or 0), s[1]["id"])}
        scored.sort(key=orders.get(sort) or (lambda s: (-s[0], -rate(s[1]), s[1]["id"])))
        return {"products": [self._card(r) for _, r in scored[:limit]], "relaxed": []}

    def list_categories(self) -> list[dict]:
        counts: dict[str, int] = {}
        for row in self._all():
            counts[row.get("category") or "other"] = counts.get(row.get("category") or "other", 0) + 1
        group = lambda name: "Men" if name.startswith("men") else "Women" if name.startswith("women") else "More"  # noqa: E731
        return sorted(({"name": n, "count": c, "group": group(n)} for n, c in counts.items()), key=lambda c: (-c["count"], c["name"]))

    def get_product(self, product_id) -> dict | None:
        for row in self._all():
            if str(row["id"]) == str(product_id):
                return self._card(row)
        return None
