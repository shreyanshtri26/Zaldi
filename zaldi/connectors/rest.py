"""Custom API connector: any shop with a search endpoint that returns JSON, described by a small mapping the admin fills in.

Example mapping (the admin portal builds this from dropdowns; it is stored as JSON):

    {"search_url": "https://shop.example/api/search?q={query}&limit={limit}",
     "product_url": "https://shop.example/api/products/{id}",
     "headers": {"Authorization": "Bearer ..."},
     "items_path": "data.items",
     "fields": {"id": "sku", "name": "title", "price": "pricing.sale", "currency": "pricing.currency", "image": "images.0",
                "url": "links.web", "category": "category.name", "brand": "brand", "description": "about", "rating": "rating"},
     "currency": "INR", "label": "My shop"}

Paths use dots and list positions (``images.0``). Only the admin sets these addresses, and they must be public (see ``netguard``).
"""
import json
import time
import urllib.parse

import requests

from zaldi.connectors.base import SEARCH
from zaldi.connectors.catalogue import dig, make_card, rank
from zaldi.connectors.netguard import check_public_url
from zaldi.errors import ValidationError

TIMEOUT = 12
TTL = 300
REQUIRED_FIELDS = ("id", "name", "price")


def validate(config: dict) -> dict:
    """The mapping, checked. Raises ``ValueError`` (shown to the admin) naming what is missing."""
    if not isinstance(config, dict):
        raise ValueError("the API mapping must be a JSON object")
    if "{query}" not in str(config.get("search_url", "")):
        raise ValueError("search_url must contain {query}")
    fields = config.get("fields")
    if not isinstance(fields, dict) or any(not fields.get(f) for f in REQUIRED_FIELDS):
        raise ValueError("fields must map at least id, name and price")
    if "{id}" not in str(config.get("product_url", "{id}")):
        raise ValueError("product_url must contain {id}")
    if not isinstance(config.get("headers", {}), dict):
        raise ValueError("headers must be an object")
    return config


class RestStore:
    name = "rest"
    capabilities = frozenset({SEARCH})

    def __init__(self, config: dict | str, http=requests, clock=time.monotonic) -> None:
        self.config = validate(json.loads(config) if isinstance(config, str) else config)
        self.http, self.clock = http, clock
        self._cache: dict[str, tuple[float, object]] = {}

    def _get(self, url: str):
        hit = self._cache.get(url)
        if hit and self.clock() - hit[0] < TTL:
            return hit[1]
        try:
            check_public_url(url)
            response = self.http.get(url, headers={str(k): str(v) for k, v in self.config.get("headers", {}).items()}, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except ValidationError:
            raise
        except Exception as exc:
            if hit:
                return hit[1]
            raise ValidationError("the store's API is not reachable right now") from exc
        self._cache[url] = (self.clock(), data)
        return data

    def _card(self, row) -> dict | None:
        fields = self.config["fields"]
        get = lambda key: dig(row, fields[key]) if fields.get(key) else None  # noqa: E731
        stock = get("in_stock")
        return make_card(get("id"), get("name"), get("price"), get("currency") or self.config.get("currency", "INR"),
                         category=get("category") or "", brand=get("brand") or "", image=get("image"), url=get("url"),
                         description=get("description") or "", rating=get("rating"), rating_count=get("rating_count"),
                         in_stock=(not str(stock).strip().lower() in ("0", "false", "no", "out of stock")) if stock is not None else None,
                         source=self.config.get("label", ""))

    def _items(self, data) -> list:
        path = self.config.get("items_path")
        items = dig(data, path) if path else data
        return items if isinstance(items, list) else []

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        url = self.config["search_url"].format(query=urllib.parse.quote(query or "", safe=""), limit=max(limit, 20))
        cards = [c for c in (self._card(r) for r in self._items(self._get(url))[:100]) if c]
        return {"products": rank(cards, query or "", filters, limit), "relaxed": []}

    def get_product(self, product_id) -> dict | None:
        template = self.config.get("product_url")
        if not template:
            return None
        try:
            data = self._get(template.format(id=urllib.parse.quote(str(product_id), safe="")))
        except ValidationError:
            return None
        return self._card(dig(data, self.config["item_path"]) if self.config.get("item_path") else data)
