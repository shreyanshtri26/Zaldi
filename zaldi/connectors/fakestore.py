"""Fake Store API (https://fakestoreapi.com, source: github.com/keikaavousi/fake-store-api): a free demo catalogue, no key.

A good stand-in for "any other store": it proves the agent works against a catalogue it did not ship with. The API has no
search and no stock counts, so this connector fetches the product list once (cached for ``TTL`` seconds), searches it
itself, and reports availability as unknown. It is catalogue-only: cards have no buy link and the agent gets no cart tools.
"""
import re
import time

import requests

from zaldi.connectors.base import SEARCH, safe_url
from zaldi.errors import ValidationError

BASE_URL = "https://fakestoreapi.com"
TIMEOUT = 10
TTL = 600  # seconds the product list is reused, so repeated questions cost no request
DESCRIPTION_LIMIT = 240
STOPWORDS = {"show", "find", "give", "want", "need", "looking", "some", "the", "and", "for", "with", "under", "below", "above",
             "over", "than", "less", "more", "me", "please", "any", "can", "you", "have", "has", "best", "good", "cheap", "cheaper",
             "cheapest", "compare", "between", "which", "one", "what", "are", "your", "all"}


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


class FakeStore:
    name = "fakestore"
    capabilities = frozenset({SEARCH})

    def __init__(self, base_url: str = BASE_URL, http=requests, clock=time.monotonic) -> None:
        self.base, self.http, self.clock = base_url.rstrip("/"), http, clock
        self._cache: tuple[float, list[dict]] | None = None

    def _all(self) -> list[dict]:
        if self._cache and self.clock() - self._cache[0] < TTL:
            return self._cache[1]
        try:
            response = self.http.get(f"{self.base}/products", timeout=TIMEOUT)
            response.raise_for_status()
            rows = response.json()
        except Exception as exc:
            if self._cache:
                return self._cache[1]  # a stale list beats failing the shopper's question
            raise ValidationError("the store is not reachable right now") from exc
        self._cache = (self.clock(), rows)
        return rows

    @staticmethod
    def _card(row: dict) -> dict:
        return {
            "id": row["id"], "product_name": row.get("title") or "", "brand": "", "category": row.get("category") or "", "color": "",
            "size": "", "material": "", "price": row.get("price") or 0, "currency": "USD",
            "stock_quantity": None,  # this API does not report stock: unknown, not "in stock"
            "image_url": safe_url(row.get("image")), "description": " ".join((row.get("description") or "").split())[:DESCRIPTION_LIMIT],
            "rating": (row.get("rating") or {}).get("rate"), "catalogue_only": True,
        }

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        terms = [_stem(w) for w in re.findall(r"[a-z']+", query.lower()) if w not in STOPWORDS and len(w) > 2]
        low, high = (filters or {}).get("min_price"), (filters or {}).get("max_price")
        scored = []
        for row in self._all():
            if (low and row["price"] < low) or (high and row["price"] > high):
                continue
            title, category, about = (set(_stem(w) for w in re.findall(r"[a-z']+", row.get(k, "").lower())) for k in ("title", "category", "description"))
            score = sum(3 * (t in title) + 2 * (t in category) + (t in about) for t in terms)  # whole words: "men's" must not match "women's"
            if re.search(r"(?<![a-z])" + re.escape(row.get("category", "").lower()), query.lower()):
                score += 6  # the shopper named this exact category
            if score or not terms:
                scored.append((score, (row.get("rating") or {}).get("rate") or 0, row))
        scored.sort(key=lambda s: (-s[0], -s[1], s[2]["id"]))
        return {"products": [self._card(r) for _, _, r in scored[:limit]], "relaxed": []}

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
