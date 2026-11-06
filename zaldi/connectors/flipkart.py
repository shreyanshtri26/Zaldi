"""Flipkart connector (Flipkart Affiliate API). Catalogue and link-out only.

Needs a Flipkart Affiliate account: your Affiliate Tracking ID and API token, sent as the ``Fk-Affiliate-Id`` and ``Fk-Affiliate-Token``
headers. Every card links to Flipkart's own page (``productUrl``) and says "from Flipkart"; nothing is added to a cart or ordered here.

STATUS: written from Flipkart's published API pages (base ``https://affiliate-api.flipkart.net/affiliate/``, search at
``1.0/search.json?query=...&resultCount=...``, product at ``product/json?id=...``). The published reference showed the product feed's
field names (``productBaseInfoV1`` with ``productId``, ``title``, ``imageUrls``, ``flipkartSellingPrice``, ``maximumRetailPrice``,
``productUrl``, ``inStock``, ``categoryPath``) but not the search response itself, so the parser accepts the list under ``products`` or
``productInfoList`` and both ``productBaseInfoV1`` and ``productBaseInfo.productAttributes``. Tested against recorded samples only: run
``python scripts/check_marketplaces.py --live`` with real keys to print the true response shape.
"""
import json
import time

import requests

from zaldi.connectors.base import SEARCH
from zaldi.connectors.catalogue import dig, dig_any, make_card, rank
from zaldi.errors import ValidationError

API_BASE = "https://affiliate-api.flipkart.net/affiliate"
TIMEOUT = 12
CACHE_TTL = 600
IMAGE_SIZES = ("800x800", "400x400", "200x200")


def _image(urls) -> str | None:
    if isinstance(urls, dict):
        return next((urls[s] for s in IMAGE_SIZES if urls.get(s)), next(iter(urls.values()), None))
    return urls[0] if isinstance(urls, list) and urls else urls if isinstance(urls, str) else None


def _category(path) -> str:
    """``categoryPath`` is a JSON-encoded string in the feed (a list of ``{"title": ...}`` groups) or plain ``A>B>C`` text."""
    if isinstance(path, str):
        try:
            path = json.loads(path)
        except ValueError:
            return path.split(">")[-1].strip()
    flat = [step.get("title", "") for group in (path if isinstance(path, list) else []) for step in (group if isinstance(group, list) else [group]) if isinstance(step, dict)]
    return flat[-1] if flat else ""


class FlipkartStore:
    name = "flipkart"
    capabilities = frozenset({SEARCH})

    def __init__(self, affiliate_id: str, token: str, api_base: str = API_BASE, http=requests, clock=time.monotonic) -> None:
        if not (affiliate_id and token):
            raise ValueError("flipkart_affiliate_id and flipkart_token are required")
        self.headers = {"Fk-Affiliate-Id": affiliate_id, "Fk-Affiliate-Token": token}
        self.base, self.http, self.clock = api_base.rstrip("/"), http, clock
        self._cache: dict[str, tuple[float, object]] = {}

    def _get(self, path: str, params: dict):
        key = path + repr(sorted(params.items()))
        hit = self._cache.get(key)
        if hit and self.clock() - hit[0] < CACHE_TTL:
            return hit[1]
        try:
            response = self.http.get(f"{self.base}{path}", params=params, headers=self.headers, timeout=TIMEOUT)
            if response.status_code in (401, 403):
                raise ValidationError("Flipkart refused the affiliate id or token")
            response.raise_for_status()
            data = response.json()
        except ValidationError:
            raise
        except Exception as exc:
            if hit:
                return hit[1]
            raise ValidationError("Flipkart is not reachable right now") from exc
        self._cache[key] = (self.clock(), data)
        return data

    @staticmethod
    def _base(item: dict) -> dict:
        return dig_any(item, "productBaseInfoV1", "productBaseInfo.productAttributes", default=item)

    def _card(self, item) -> dict | None:
        if not isinstance(item, dict):
            return None
        b = self._base(item)
        return make_card(
            (dig_any(b, "productId", "id") or item.get("productId")), dig_any(b, "title", "productTitle"),
            dig_any(b, "flipkartSpecialPrice.amount", "flipkartSellingPrice.amount", "sellingPrice.amount", "maximumRetailPrice.amount"),
            dig_any(b, "flipkartSellingPrice.currency", "maximumRetailPrice.currency", default="INR"),
            category=_category(b.get("categoryPath")), brand=b.get("productBrand") or "", image=_image(b.get("imageUrls")),
            url=b.get("productUrl"), description=b.get("productDescription") or "", in_stock=b.get("inStock") if isinstance(b.get("inStock"), bool) else None,
            source="Flipkart")

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        data = self._get("/1.0/search.json", {"query": (query or "").strip() or "bestseller", "resultCount": 10})
        items = dig_any(data, "products", "productInfoList", default=[])
        cards = [c for c in (self._card(i) for i in items) if c]
        return {"products": rank(cards, query or "", filters, limit) if (query or "").strip() else cards[:limit], "relaxed": []}

    def get_product(self, product_id) -> dict | None:
        try:
            data = self._get("/product/json", {"id": str(product_id)})
        except ValidationError:
            return None
        return self._card(dig(data, "productInfo") or dig(data, "product") or data)
