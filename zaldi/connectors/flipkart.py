"""Flipkart connector (Flipkart Affiliate API). Catalogue and link-out only.

Needs a Flipkart Affiliate account: your Affiliate Tracking ID and API token, sent as the ``Fk-Affiliate-Id`` and ``Fk-Affiliate-Token``
headers. Every card links to Flipkart's own page (``productUrl``, which already carries your affiliate id) and says "from Flipkart";
nothing is added to a cart or ordered here.

Built from Flipkart's Product APIs reference (base ``https://affiliate-api.flipkart.net/affiliate``):

* **Search:** ``GET 1.0/search.json?query=...&resultCount=...`` (at most 10 results). Response: ``productInfoList[]`` whose items have
  ``productBaseInfoV1`` (``productId``, ``title``, ``productDescription``, ``imageUrls`` keyed by size, ``maximumRetailPrice``,
  ``flipkartSellingPrice``, ``flipkartSpecialPrice``, ``productUrl``, ``productBrand``, ``inStock``, ``categoryPath`` as a JSON string,
  ``attributes.{size,color}``).
* **Product by id:** ``GET 1.0/product.json?id=...``; the response is the ``productBaseInfoV1`` block itself.
* The older (legacy) shape, ``productBaseInfo.{productIdentifier, productAttributes}`` with ``sellingPrice``, is read too.

STATUS: tested against responses shaped like the documentation's samples, not against live Flipkart (no affiliate account was available).
Check yours with ``python scripts/check_marketplaces.py --live``, which prints the real response shape.
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
MAX_RESULTS = 10  # the API returns at most ten products per search
IMAGE_SIZES = ("800x800", "400x400", "200x200")


def _image(urls) -> str | None:
    if isinstance(urls, dict):
        return next((urls[s] for s in IMAGE_SIZES if urls.get(s)), next((v for v in urls.values() if v), None))
    return urls[0] if isinstance(urls, list) and urls else urls if isinstance(urls, str) else None


def _category(path) -> str:
    """The last step of the category path. The current API sends it as a JSON string of nested lists of ``{"title": ...}``, the legacy one as
    nested lists already, and some feeds as plain ``A>B>C`` text."""
    if isinstance(path, str):
        try:
            path = json.loads(path)
        except ValueError:
            return path.split(">")[-1].strip()

    def titles(node):
        if isinstance(node, dict):
            return [str(node["title"])] if node.get("title") else []
        return [t for child in node for t in titles(child)] if isinstance(node, list) else []

    flat = titles(path)
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
        """The block with the product's fields: ``productBaseInfoV1`` (current), or ``productBaseInfo.productAttributes`` (legacy)."""
        return dig_any(item, "productBaseInfoV1", "productBaseInfo.productAttributes", default=item)

    def _card(self, item) -> dict | None:
        if not isinstance(item, dict):
            return None
        b = self._base(item)
        attributes = b.get("attributes") if isinstance(b.get("attributes"), dict) else {}
        stock = b.get("inStock")
        return make_card(
            dig_any(b, "productId", "id") or dig(item, "productBaseInfo.productIdentifier.productId") or item.get("productId"),
            dig_any(b, "title", "productTitle"),
            dig_any(b, "flipkartSpecialPrice.amount", "flipkartSellingPrice.amount", "sellingPrice.amount", "maximumRetailPrice.amount"),
            dig_any(b, "flipkartSpecialPrice.currency", "flipkartSellingPrice.currency", "sellingPrice.currency", "maximumRetailPrice.currency", default="INR"),
            category=_category(b.get("categoryPath") or dig(item, "productBaseInfo.productIdentifier.categoryPaths.categoryPath")),
            brand=b.get("productBrand") or "", image=_image(b.get("imageUrls")), url=b.get("productUrl"), description=b.get("productDescription") or "",
            in_stock=stock if isinstance(stock, bool) else None, source="Flipkart",
            color=str(attributes.get("color") or b.get("color") or ""), size=str(attributes.get("size") or b.get("size") or ""))

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        data = self._get("/1.0/search.json", {"query": (query or "").strip() or "bestseller", "resultCount": MAX_RESULTS})
        items = dig_any(data, "productInfoList", "products", default=[])
        cards = [c for c in (self._card(i) for i in items) if c]
        return {"products": rank(cards, query or "", filters, limit) if (query or "").strip() or filters else cards[:limit], "relaxed": []}

    def get_product(self, product_id) -> dict | None:
        try:
            data = self._get("/1.0/product.json", {"id": str(product_id)})
        except ValidationError:
            return None
        first = (data.get("productInfoList") or [None])[0] if isinstance(data, dict) and data.get("productInfoList") else None
        return self._card(first or data)
