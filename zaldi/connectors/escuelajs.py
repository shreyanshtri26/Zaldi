"""Platzi Fake Store API (https://api.escuelajs.co/docs): a free demo catalogue, no key.

Uses the documented read endpoints only: ``GET /products`` (paged with ``offset``/``limit``, cached for ``TTL`` seconds) and
``GET /categories``. Text matching, price filters and ordering are done here, so the connector behaves the same however the API
filters. The API is an open sandbox that anyone can write to, so its data can contain junk (odd category names, placeholder
pictures): images are shown exactly as the API sends them (a real photo wins over a placeholder box when a product has both, and a dead
link falls back to our fabric tile in the page), and the admin can hide a category from the home page. It reports no stock, ratings or currency, so availability is unknown and prices are shown in USD. Catalogue-only: no
buy link, no cart tools. The API's write endpoints are never used.
"""
import re
import time
import urllib.parse

import requests

from zaldi.connectors.base import SEARCH, safe_url, sort_intent
from zaldi.errors import ValidationError

BASE_URL = "https://api.escuelajs.co/api/v1"
TIMEOUT = 10
TTL = 600  # seconds a fetched page is reused, so repeated questions cost no request
PAGE = 100  # products per request
MAX_PRODUCTS = 500  # the demo catalogue is small; this only guards against a runaway listing
DESCRIPTION_LIMIT = 240
PLACEHOLDER_HOSTS = ("placehold.co", "placeimg.com", "via.placeholder.com", "dummyimage.com", "picsum.photos")
URL_IN_TEXT = re.compile(r"https?://[^\s\"'\[\]]+")
STOPWORDS = {"show", "find", "give", "want", "need", "looking", "some", "the", "and", "for", "with", "under", "below", "above",
             "over", "than", "less", "more", "me", "please", "any", "can", "you", "have", "has", "best", "good", "cheap", "cheaper",
             "cheapest", "compare", "between", "which", "one", "what", "are", "your", "all", "top", "rated", "most", "expensive",
             "lowest", "price", "highest", "popular", "premium"}


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _image(images, real_only: bool = False) -> str | None:
    """The picture to show: what the API sent. Entries are usually URLs but sometimes JSON-looking text. A real photo wins over a
    placeholder box; with ``real_only`` placeholders are skipped (a category tile looks better as a fabric tile than as a grey box)."""
    urls = [u for entry in images or [] for u in URL_IN_TEXT.findall(str(entry)) if safe_url(u)]
    real = [u for u in urls if not urllib.parse.urlparse(u).netloc.lower().endswith(PLACEHOLDER_HOSTS)]
    return (real or ([] if real_only else urls) or [None])[0]


class EscuelaStore:
    name = "escuelajs"
    capabilities = frozenset({SEARCH})

    def __init__(self, base_url: str = BASE_URL, http=requests, clock=time.monotonic) -> None:
        self.base, self.http, self.clock = base_url.rstrip("/"), http, clock
        self._cache: dict[str, tuple[float, object]] = {}

    def _fetch(self, path: str, params: dict | None = None):
        """GET a JSON endpoint, cached. A stale copy beats failing the shopper's question when the API is down."""
        key = path + "?" + urllib.parse.urlencode(sorted((params or {}).items()))
        hit = self._cache.get(key)
        if hit and self.clock() - hit[0] < TTL:
            return hit[1]
        try:
            response = self.http.get(f"{self.base}{path}", params=params, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            if hit:
                return hit[1]
            raise ValidationError("the store is not reachable right now") from exc
        self._cache[key] = (self.clock(), data)
        return data

    def _all(self) -> list[dict]:
        rows: list[dict] = []
        offset = 0  # counts rows the API returned, not rows we kept: dropped items must not shift the next page
        while offset < MAX_PRODUCTS:
            page = self._fetch("/products", {"offset": offset, "limit": PAGE})
            rows += [r for r in page if isinstance(r, dict) and r.get("title") and (r.get("price") or 0) > 0]
            offset += len(page)
            if len(page) < PAGE:
                break
        return rows

    @staticmethod
    def _category(row: dict) -> str:
        return ((row.get("category") or {}).get("name") or "").strip()

    def _named_category(self, query: str, rows: list[dict]) -> str | None:
        """A category the shopper named exactly (whole words, longest name first, so "shoes" never matches inside another word)."""
        for name in sorted({self._category(r) for r in rows if self._category(r)}, key=len, reverse=True):
            if re.search(r"(?<![a-z0-9])" + re.escape(name.lower()) + r"(?![a-z0-9])", query.lower()):
                return name
        return None

    def _card(self, row: dict) -> dict:
        return {
            "id": row["id"], "product_name": row["title"].strip(), "brand": "", "category": self._category(row), "color": "",
            "size": "", "material": "", "price": row.get("price") or 0, "currency": "USD",
            "stock_quantity": None,  # this API does not report stock: unknown, not "in stock"
            "image_url": _image(row.get("images")), "description": " ".join((row.get("description") or "").split())[:DESCRIPTION_LIMIT],
            "catalogue_only": True,
        }

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        filters = filters or {}
        rows = self._all()
        sort = filters.get("sort") or sort_intent(query)
        category = filters.get("category") or self._named_category(query, rows)
        terms = [_stem(w) for w in re.findall(r"[a-z0-9']+", query.lower()) if w not in STOPWORDS and len(w) > 2 and not w.isdigit()]
        low, high = filters.get("min_price"), filters.get("max_price")
        scored, in_budget = [], []
        for row in rows:
            if category and self._category(row).lower() != category.lower():
                continue
            if (low and row["price"] < low) or (high and row["price"] > high):
                continue
            title, cat, about = (set(_stem(w) for w in re.findall(r"[a-z0-9']+", text.lower())) for text in
                                 (row["title"], self._category(row), row.get("description") or ""))
            score = sum(3 * (t in title) + 2 * (t in cat) + (t in about) for t in terms)
            in_budget.append((score, row))
            if score or not terms or category:  # a named category already narrowed the pool
                scored.append((score, row))
        if sort and not scored:  # "show me the cheapest": an ordering with nothing else named applies to the whole catalogue
            scored = in_budget
        orders = {"price_asc": lambda s: (s[1]["price"], s[1]["id"]), "price_desc": lambda s: (-s[1]["price"], s[1]["id"])}
        scored.sort(key=orders.get(sort) or (lambda s: (-s[0], s[1]["id"])))  # no ratings here: "top rated" falls back to relevance
        return {"products": [self._card(r) for _, r in scored[:limit]], "relaxed": []}

    def list_categories(self) -> list[dict]:
        counts: dict[str, int] = {}
        pictures: dict[str, str] = {}
        for row in self._all():
            name = self._category(row)
            if name:
                counts[name] = counts.get(name, 0) + 1  # empty categories are left out
                if name not in pictures and _image(row.get("images"), real_only=True):
                    pictures[name] = _image(row.get("images"), real_only=True)
        return sorted(({"name": n, "count": c, "group": "More", "image": pictures.get(n)} for n, c in counts.items()), key=lambda c: (-c["count"], c["name"]))

    def get_product(self, product_id) -> dict | None:
        for row in self._all():
            if str(row["id"]) == str(product_id):
                return self._card(row)
        try:
            row = self._fetch(f"/products/{int(product_id)}")
            return self._card(row) if row.get("title") and (row.get("price") or 0) > 0 else None
        except (ValueError, ValidationError, KeyError, TypeError, AttributeError):
            return None
