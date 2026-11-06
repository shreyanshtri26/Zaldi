"""WooCommerce, read-only: product search and details through the store's REST API (``/wp-json/wc/v3``).

The shopper buys on the store itself: every card carries the product page link (``buy_url``), so no cart state or payment
data ever passes through Zaldi. Credentials are a read-only consumer key and secret (WooCommerce -> Settings -> Advanced ->
REST API), sent as HTTP basic auth, which WooCommerce only accepts over HTTPS.
"""
import html
import re

import requests

from zaldi.connectors.base import SEARCH, safe_url
from zaldi.errors import ValidationError

TIMEOUT = 10  # seconds; the agent must stay responsive when a store is slow
DESCRIPTION_LIMIT = 240


def _text(raw: str | None) -> str:
    """Store descriptions are HTML: strip tags and entities, collapse whitespace, and keep it short."""
    plain = html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    return " ".join(plain.split())[:DESCRIPTION_LIMIT]


def _attribute(row: dict, *names: str) -> str:
    for attr in row.get("attributes") or []:
        if (attr.get("name") or "").lower() in names:
            return ", ".join(attr.get("options") or [])
    return ""


class WooStore:
    name = "woocommerce"
    capabilities = frozenset({SEARCH})

    def __init__(self, base_url: str, key: str, secret: str, http=requests) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("WOOCOMMERCE_URL must start with https:// (WooCommerce basic auth needs HTTPS)")
        if not key or not secret:
            raise ValueError("WOOCOMMERCE_KEY and WOOCOMMERCE_SECRET are required")
        self.base, self.auth, self.http = base_url.rstrip("/"), (key, secret), http

    def _get(self, path: str, params: dict | None = None):
        try:
            response = self.http.get(f"{self.base}/wp-json/wc/v3/{path}", params=params, auth=self.auth, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # network, auth or store errors: say so plainly, never leak the URL or key
            raise ValidationError("the store is not reachable right now") from exc

    @staticmethod
    def _card(row: dict) -> dict:
        stock = row.get("stock_quantity")
        return {
            "id": row["id"], "product_name": row.get("name") or "", "brand": _attribute(row, "brand"),
            "category": ((row.get("categories") or [{}])[0].get("name") or ""), "color": _attribute(row, "color", "colour"),
            "size": _attribute(row, "size"), "material": _attribute(row, "material"),
            "price": int(float(row.get("price") or 0)), "stock_quantity": stock if stock is not None else (1 if row.get("stock_status") == "instock" else 0),
            "image_url": safe_url((row.get("images") or [{}])[0].get("src")), "description": _text(row.get("short_description") or row.get("description")),
            "buy_url": safe_url(row.get("permalink")),
        }

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        params = {"search": query, "per_page": limit, "status": "publish"}
        for key in ("min_price", "max_price"):
            if (filters or {}).get(key):
                params[key] = filters[key]
        return {"products": [self._card(r) for r in self._get("products", params)], "relaxed": []}

    def list_categories(self) -> list[dict]:
        rows = self._get("products/categories", {"per_page": 50, "hide_empty": "true"})
        return [{"name": html.unescape(r["name"]), "count": r.get("count", 0), "group": "More", "image": safe_url((r.get("image") or {}).get("src"))}
                for r in rows if r.get("count")]

    def get_product(self, product_id) -> dict | None:
        try:
            return self._card(self._get(f"products/{int(product_id)}"))
        except (ValueError, ValidationError):
            return None
