"""Shopify, read-only: product search through the Storefront GraphQL API.

The Storefront access token is a public, read-only token (Shopify admin -> Apps -> Develop apps -> Storefront API). Each card
links to the product page on the store (``buy_url``), so the shopper buys on Shopify and no cart or payment data passes
through Zaldi. Only ``SEARCH`` is advertised: the agent is not given cart tools for this store.
"""
import re

import requests

from zaldi.connectors.base import SEARCH, safe_url
from zaldi.errors import ValidationError

TIMEOUT = 10
DESCRIPTION_LIMIT = 240
SHOP_DOMAIN = re.compile(r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$", re.I)
FIELDS = """id title vendor productType description onlineStoreUrl availableForSale
  featuredImage { url } priceRange { minVariantPrice { amount currencyCode } } options { name values }"""
SEARCH_QUERY = "query($q: String!, $n: Int!) { products(first: $n, query: $q) { nodes { %s } } }" % FIELDS
ONE_QUERY = "query($id: ID!) { product(id: $id) { %s } }" % FIELDS


def _option(node: dict, *names: str) -> str:
    for option in node.get("options") or []:
        if (option.get("name") or "").lower() in names:
            return ", ".join(option.get("values") or [])
    return ""


class ShopifyStore:
    name = "shopify"
    capabilities = frozenset({SEARCH})

    def __init__(self, domain: str, token: str, api_version: str, http=requests) -> None:
        if not SHOP_DOMAIN.match(domain or ""):
            raise ValueError("SHOPIFY_DOMAIN must look like your-store.myshopify.com")
        if not token:
            raise ValueError("SHOPIFY_STOREFRONT_TOKEN is required")
        self.url = f"https://{domain}/api/{api_version}/graphql.json"
        self.headers = {"X-Shopify-Storefront-Access-Token": token, "Content-Type": "application/json"}
        self.http = http

    def _query(self, query: str, variables: dict) -> dict:
        try:
            response = self.http.post(self.url, json={"query": query, "variables": variables}, headers=self.headers, timeout=TIMEOUT)
            response.raise_for_status()
            body = response.json()
        except Exception as exc:  # never leak the token or URL
            raise ValidationError("the store is not reachable right now") from exc
        if body.get("errors"):
            raise ValidationError("the store could not run that search")
        return body["data"]

    @staticmethod
    def _card(node: dict) -> dict:
        price = (node.get("priceRange") or {}).get("minVariantPrice") or {}
        return {
            "id": node["id"], "product_name": node.get("title") or "", "brand": node.get("vendor") or "",
            "category": node.get("productType") or "", "color": _option(node, "color", "colour"), "size": _option(node, "size"),
            "material": _option(node, "material"), "price": int(float(price.get("amount") or 0)),
            "stock_quantity": 1 if node.get("availableForSale") else 0,  # Storefront exposes availability, not counts
            "image_url": safe_url((node.get("featuredImage") or {}).get("url")), "description": " ".join((node.get("description") or "").split())[:DESCRIPTION_LIMIT],
            "buy_url": safe_url(node.get("onlineStoreUrl")),
        }

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        nodes = self._query(SEARCH_QUERY, {"q": query, "n": min(limit * 3, 30)})["products"]["nodes"]
        cards = [self._card(n) for n in nodes]
        low, high = (filters or {}).get("min_price"), (filters or {}).get("max_price")
        cards = [c for c in cards if (not low or c["price"] >= low) and (not high or c["price"] <= high)]  # budget applied here
        return {"products": cards[:limit], "relaxed": []}

    def get_product(self, product_id) -> dict | None:
        node = self._query(ONE_QUERY, {"id": str(product_id)})["product"]
        return self._card(node) if node else None
