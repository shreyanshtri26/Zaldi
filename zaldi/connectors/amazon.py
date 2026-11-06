"""Amazon connector (Creators API, the successor to the retired PA-API 5). Catalogue and link-out only.

Needs an Amazon Associates account: a Credential ID and Secret, your partner (tracking) tag, the marketplace (``www.amazon.in`` for
India) and the token endpoint shown with your credentials. Every card links to Amazon's own page (``detailPageUrl`` already carries your
tag) and says "from Amazon"; this connector never adds to a cart or places an order.

STATUS: written from Amazon's published Creators API pages (OAuth client-credentials token, ``POST catalog/v1/searchItems`` and
``getItems``, bearer token plus ``x-marketplace`` header). The documentation did not publish the full response schema, so field
lookups accept both the camelCase and PA-API spellings. It has been tested against recorded sample responses only: run
``python scripts/check_marketplaces.py --live`` with real keys, which prints the raw response shape so any difference is easy to fix.
"""
import time

import requests

from zaldi.connectors.base import SEARCH
from zaldi.connectors.catalogue import dig_any, make_card, rank
from zaldi.errors import ValidationError

API_BASE = "https://creatorsapi.amazon"
TIMEOUT = 12
CACHE_TTL = 600  # prices are never reused longer than ten minutes
RESOURCES = ["itemInfo.title", "itemInfo.byLineInfo", "itemInfo.features", "images.primary.large", "offersV2.listings.price"]


class AmazonStore:
    name = "amazon"
    capabilities = frozenset({SEARCH})

    def __init__(self, credential_id: str, credential_secret: str, partner_tag: str, token_url: str, marketplace: str = "www.amazon.in",
                 api_base: str = API_BASE, http=requests, clock=time.monotonic) -> None:
        if not (credential_id and credential_secret and partner_tag and token_url):
            raise ValueError("amazon_credential_id, amazon_credential_secret, amazon_partner_tag and amazon_token_url are required")
        self.id, self.secret, self.tag, self.token_url = credential_id, credential_secret, partner_tag, token_url
        self.marketplace, self.base, self.http, self.clock = marketplace, api_base.rstrip("/"), http, clock
        self._token: tuple[float, str] | None = None
        self._cache: dict[str, tuple[float, object]] = {}

    def _bearer(self, force: bool = False) -> str:
        if self._token and not force and self.clock() < self._token[0]:
            return self._token[1]
        try:
            response = self.http.post(self.token_url, json={"grant_type": "client_credentials", "client_id": self.id,
                                                            "client_secret": self.secret, "scope": "creatorsapi::default"}, timeout=TIMEOUT)
            response.raise_for_status()
            body = response.json()
            self._token = (self.clock() + max(60, int(body.get("expires_in", 3600)) - 120), body["access_token"])
        except Exception as exc:
            raise ValidationError("could not sign in to Amazon: check the credential id, secret and token endpoint") from exc
        return self._token[1]

    def _post(self, path: str, body: dict):
        key = path + repr(sorted(body.items(), key=lambda kv: kv[0]))
        hit = self._cache.get(key)
        if hit and self.clock() - hit[0] < CACHE_TTL:
            return hit[1]
        for attempt in (1, 2):  # the second try uses a fresh token, in case the first had expired
            try:
                response = self.http.post(f"{self.base}{path}", json=body, timeout=TIMEOUT,
                                          headers={"Authorization": f"Bearer {self._bearer(force=attempt == 2)}", "x-marketplace": self.marketplace,
                                                   "Content-Type": "application/json"})
                if response.status_code == 401 and attempt == 1:
                    continue
                response.raise_for_status()
                data = response.json()
                self._cache[key] = (self.clock(), data)
                return data
            except ValidationError:
                raise
            except Exception as exc:
                if hit:
                    return hit[1]
                raise ValidationError("Amazon is not reachable right now") from exc

    def _card(self, item: dict) -> dict | None:
        features = dig_any(item, "itemInfo.features.displayValues", "ItemInfo.Features.DisplayValues", default=[])
        return make_card(
            dig_any(item, "asin", "ASIN"), dig_any(item, "itemInfo.title.displayValue", "ItemInfo.Title.DisplayValue"),
            dig_any(item, "offersV2.listings.0.price.money.amount", "offersV2.listings.0.price.amount", "offers.listings.0.price.amount",
                    "Offers.Listings.0.Price.Amount"),
            dig_any(item, "offersV2.listings.0.price.money.currency", "offersV2.listings.0.price.currency", "Offers.Listings.0.Price.Currency", default="INR"),
            brand=dig_any(item, "itemInfo.byLineInfo.brand.displayValue", "ItemInfo.ByLineInfo.Brand.DisplayValue", default=""),
            image=dig_any(item, "images.primary.large.url", "Images.Primary.Large.URL", "images.primary.medium.url"),
            url=dig_any(item, "detailPageUrl", "DetailPageURL"), description=" ".join(features[:3]) if isinstance(features, list) else "",
            source="Amazon")

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        data = self._post("/catalog/v1/searchItems", {"keywords": (query or "").strip() or "bestseller", "partnerTag": self.tag,
                                                      "marketplace": self.marketplace, "resources": RESOURCES, "itemCount": 10})
        items = dig_any(data, "searchResult.items", "SearchResult.Items", "items", default=[])
        cards = [c for c in (self._card(i) for i in items if isinstance(i, dict)) if c]
        return {"products": rank(cards, query or "", filters, limit) if (query or "").strip() else cards[:limit], "relaxed": []}

    def get_product(self, product_id) -> dict | None:
        try:
            data = self._post("/catalog/v1/getItems", {"itemIds": [str(product_id)], "itemIdType": "ASIN", "partnerTag": self.tag,
                                                       "marketplace": self.marketplace, "resources": RESOURCES})
        except ValidationError:
            return None
        items = dig_any(data, "itemsResult.items", "ItemsResult.Items", "items", default=[])
        return self._card(items[0]) if items and isinstance(items[0], dict) else None
