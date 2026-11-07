"""Amazon connector (Creators API, the successor to the retired PA-API 5). Catalogue and link-out only.

Needs an Amazon Associates account with Creators API access: a Credential ID and Secret, your partner (tracking) tag and the marketplace
(``www.amazon.in`` for India). Every card links to Amazon's own page (``detailPageURL`` already carries your tag) and says "from Amazon";
this connector never adds to a cart or places an order.

Built from Amazon's Creators API documentation:

* **Sign-in:** OAuth2 client credentials, ``POST`` JSON ``{grant_type, client_id, client_secret, scope: "creatorsapi::default"}`` to the
  token address of your marketplace's region (``TOKEN_URLS`` below; for India that is ``https://api.amazon.co.uk/auth/o2/token``). A token
  lasts an hour and is reused.
* **Search:** ``POST https://creatorsapi.amazon/catalog/v1/searchItems`` with ``Authorization: Bearer ...`` and ``x-marketplace``. Body:
  ``partnerTag``, ``keywords``, ``itemCount`` (1 to 10), ``sortBy``, ``minPrice``/``maxPrice`` (in the currency's smallest unit),
  ``resources``. Response: ``searchResult.items[]`` with ``asin``, ``detailPageURL``, ``itemInfo.title.displayValue``,
  ``images.primary.{small,medium,large}.url`` and ``offersV2.listings[]`` (``price.money.amount``/``currency``, ``availability.type``,
  ``isBuyBoxWinner``).

STATUS: tested against responses shaped like the documentation's samples, not against live Amazon (no Associates account was available).
Details the documentation does not show (the brand and feature fields, ``getItems``) are read tolerantly. Check yours with
``python scripts/check_marketplaces.py --live``, which prints the real response shape.
"""
import time

import requests

from zaldi.connectors.base import SEARCH
from zaldi.connectors.catalogue import dig, dig_any, make_card, rank
from zaldi.errors import ValidationError

API_BASE = "https://creatorsapi.amazon"
TIMEOUT = 12
CACHE_TTL = 600  # prices are never reused longer than ten minutes
RESOURCES = ["itemInfo.title", "itemInfo.byLineInfo", "itemInfo.features", "images.primary.large", "offersV2.listings.price"]
SORTS = {"price_asc": "Price:LowToHigh", "price_desc": "Price:HighToLow", "rating": "AvgCustomerReviews"}
# The token address depends on the marketplace's region (credential versions 3.1, 3.2 and 3.3 in Amazon's documentation).
TOKEN_URLS = {"NA": "https://api.amazon.com/auth/o2/token", "EU": "https://api.amazon.co.uk/auth/o2/token", "FE": "https://api.amazon.co.jp/auth/o2/token"}
REGIONS = {"NA": ("com", "ca", "com.mx", "com.br"),
           "EU": ("co.uk", "de", "fr", "it", "es", "nl", "com.be", "eg", "in", "ie", "pl", "sa", "se", "com.tr", "ae"),
           "FE": ("co.jp", "sg", "com.au")}
NO_MINOR_UNITS = ("co.jp",)  # yen has no smaller unit; every other supported marketplace uses hundredths


def token_url_for(marketplace: str) -> str:
    """The token address for a marketplace such as ``www.amazon.in``; the North American one if the domain is not recognised."""
    domain = (marketplace or "").lower().removeprefix("www.").removeprefix("amazon.")
    return TOKEN_URLS[next((region for region, domains in REGIONS.items() if domain in domains), "NA")]


class AmazonStore:
    name = "amazon"
    capabilities = frozenset({SEARCH})

    def __init__(self, credential_id: str, credential_secret: str, partner_tag: str, token_url: str = "", marketplace: str = "www.amazon.in",
                 api_base: str = API_BASE, http=requests, clock=time.monotonic) -> None:
        if not (credential_id and credential_secret and partner_tag):
            raise ValueError("amazon_credential_id, amazon_credential_secret and amazon_partner_tag are required")
        self.id, self.secret, self.tag = credential_id, credential_secret, partner_tag
        self.marketplace, self.base, self.http, self.clock = marketplace or "www.amazon.in", api_base.rstrip("/"), http, clock
        self.token_url = token_url or token_url_for(self.marketplace)  # an explicit address wins over the regional default
        self._token: tuple[float, str] | None = None
        self._cache: dict[str, tuple[float, object]] = {}

    def _bearer(self, force: bool = False) -> str:
        if self._token and not force and self.clock() < self._token[0]:
            return self._token[1]
        try:
            response = self.http.post(self.token_url, json={"grant_type": "client_credentials", "client_id": self.id,
                                                            "client_secret": self.secret, "scope": "creatorsapi::default"},
                                      headers={"Content-Type": "application/json"}, timeout=TIMEOUT)
            response.raise_for_status()
            body = response.json()
            self._token = (self.clock() + max(60, int(body.get("expires_in", 3600)) - 120), body["access_token"])
        except Exception as exc:
            raise ValidationError("could not sign in to Amazon: check the credential id and secret, and that Creators API access is approved for this marketplace") from exc
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

    @staticmethod
    def _offer(item: dict) -> dict:
        """The listing to price the card from: the buy-box winner if there is one, otherwise the first."""
        listings = dig_any(item, "offersV2.listings", "Offers.Listings", "offers.listings", default=[])
        listings = [x for x in listings if isinstance(x, dict)] if isinstance(listings, list) else []
        return next((x for x in listings if x.get("isBuyBoxWinner")), listings[0] if listings else {})

    def _card(self, item: dict) -> dict | None:
        offer = self._offer(item)
        features = dig_any(item, "itemInfo.features.displayValues", "ItemInfo.Features.DisplayValues", default=[])
        availability = str(dig(offer, "availability.type") or "").upper()
        return make_card(
            dig_any(item, "asin", "ASIN"), dig_any(item, "itemInfo.title.displayValue", "ItemInfo.Title.DisplayValue"),
            dig_any(offer, "price.money.amount", "price.amount", "Price.Amount"),
            dig_any(offer, "price.money.currency", "price.currency", "Price.Currency", default="INR"),
            brand=dig_any(item, "itemInfo.byLineInfo.brand.displayValue", "ItemInfo.ByLineInfo.Brand.DisplayValue", default=""),
            image=dig_any(item, "images.primary.large.url", "images.primary.medium.url", "images.primary.small.url", "Images.Primary.Large.URL"),
            url=dig_any(item, "detailPageURL", "detailPageUrl", "DetailPageURL"),  # the documentation spells it detailPageURL
            description=" ".join(features[:3]) if isinstance(features, list) else "",
            in_stock=False if "OUT" in availability else None, source="Amazon")

    def _body(self, query: str, filters: dict, limit: int) -> dict:
        body = {"keywords": (query or "").strip() or "bestseller", "partnerTag": self.tag, "marketplace": self.marketplace,
                "resources": RESOURCES, "itemCount": 10}
        sort = SORTS.get(filters.get("sort") or "")
        if sort:
            body["sortBy"] = sort
        unit = 1 if any(self.marketplace.endswith(d) for d in NO_MINOR_UNITS) else 100  # prices in the currency's smallest unit
        for key, field in (("min_price", "minPrice"), ("max_price", "maxPrice")):
            if filters.get(key):
                body[field] = int(filters[key] * unit)
        return body

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        filters = filters or {}
        data = self._post("/catalog/v1/searchItems", self._body(query, filters, limit))
        items = dig_any(data, "searchResult.items", "SearchResult.Items", "items", default=[])
        cards = [c for c in (self._card(i) for i in items if isinstance(i, dict)) if c]
        # Amazon applies the sort and the price range itself; the same rules are applied again here in case a filter was ignored.
        return {"products": rank(cards, query or "", filters, limit) if (query or "").strip() or filters else cards[:limit], "relaxed": []}

    def get_product(self, product_id) -> dict | None:
        try:
            data = self._post("/catalog/v1/getItems", {"itemIds": [str(product_id)], "itemIdType": "ASIN", "partnerTag": self.tag,
                                                       "marketplace": self.marketplace, "resources": RESOURCES})
        except ValidationError:
            return None
        items = dig_any(data, "itemsResult.items", "ItemsResult.Items", "items", default=[])
        return self._card(items[0]) if items and isinstance(items[0], dict) else None
