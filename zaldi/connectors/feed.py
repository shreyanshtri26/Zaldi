"""Product feed connector: read a CSV or JSON product list (Google Merchant style) from a public link or a local file.

Column names are matched by synonym (``title``/``name``/``g:title``, ``price``/``sale_price``, ``link``/``url`` ...), so most exported feeds
work as they are. The feed is fetched at most every ``TTL`` seconds; a stale copy is used if the link is down. Rows without a name, id or
price are skipped and counted, so the admin's Test step can say how many rows were unusable.
"""
import csv
import io
import json
import time
from pathlib import Path

import requests

from zaldi.connectors.catalogue import CatalogueStore, dig_any, make_card
from zaldi.connectors.netguard import check_public_url
from zaldi.errors import ValidationError

TTL = 900
TIMEOUT = 15
MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 5000
SYNONYMS = {
    "id": ("id", "g:id", "sku", "product_id", "productid", "item_id", "handle"),
    "name": ("title", "g:title", "name", "product_name", "productname"),
    "price": ("sale_price", "g:sale_price", "price", "g:price", "selling_price", "offer_price"),
    "currency": ("currency", "price_currency"),
    "category": ("product_type", "g:product_type", "category", "google_product_category", "g:google_product_category"),
    "brand": ("brand", "g:brand", "vendor", "manufacturer"),
    "image": ("image_link", "g:image_link", "image", "image_url", "images", "thumbnail"),
    "url": ("link", "g:link", "url", "product_url", "product_link"),
    "description": ("description", "g:description", "body_html", "summary"),
    "availability": ("availability", "g:availability", "in_stock", "stock_status"),
    "rating": ("rating", "average_rating", "review_rating"),
    "rating_count": ("rating_count", "review_count", "reviews"),
    "color": ("color", "g:color", "colour"),
}


def _field(row: dict, key: str):
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    return next((lowered[name] for name in SYNONYMS[key] if lowered.get(name) not in (None, "")), None)


def _in_stock(value) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("out of stock", "out_of_stock", "outofstock", "false", "0", "no", "sold out"):
        return False
    return True if text in ("in stock", "in_stock", "instock", "true", "1", "yes") or text.isdigit() else None


def parse(text: str, default_currency: str = "INR", source: str = "") -> tuple[list[dict], int]:
    """``(cards, skipped_rows)`` from CSV or JSON text. JSON may be a list or ``{"products"|"items"|"data": [...]}``."""
    text = text.lstrip("﻿").strip()
    if text[:1] in "[{":
        data = json.loads(text)
        rows = data if isinstance(data, list) else next((data[k] for k in ("products", "items", "data", "results") if isinstance(data.get(k), list)), [])
    else:
        rows = list(csv.DictReader(io.StringIO(text), delimiter="\t" if text.split("\n", 1)[0].count("\t") > text.split("\n", 1)[0].count(",") else ","))
    cards, skipped = [], 0
    for row in rows[:MAX_ROWS]:
        if not isinstance(row, dict):
            skipped += 1
            continue
        price_text = _field(row, "price")
        currency = _field(row, "currency") or (str(price_text).split()[-1] if price_text and str(price_text).split()[-1].isalpha() else default_currency)
        image = _field(row, "image")
        if isinstance(image, list):
            image = image[0] if image else None
        if isinstance(image, dict):
            image = dig_any(image, "src", "url")
        card = make_card(_field(row, "id"), _field(row, "name"), price_text, currency, category=_field(row, "category") or "",
                         brand=_field(row, "brand") or "", image=image, url=_field(row, "url"), description=_field(row, "description") or "",
                         rating=_number(_field(row, "rating")), rating_count=_number(_field(row, "rating_count")),
                         in_stock=_in_stock(_field(row, "availability")), source=source, color=_field(row, "color") or "")
        if card:
            cards.append(card)
        else:
            skipped += 1
    return cards, skipped


def _number(value):
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


class FeedStore(CatalogueStore):
    name = "feed"

    def __init__(self, source: str, currency: str = "INR", label: str = "", http=requests, clock=time.monotonic) -> None:
        if not source:
            raise ValueError("feed_url is required")
        self.source, self.currency, self.label, self.http, self.clock = source, currency, label, http, clock
        self._cached: tuple[float, list[dict], int] | None = None

    def _load(self) -> str:
        if not self.source.startswith(("http://", "https://")):
            return Path(self.source).read_text(encoding="utf-8")  # a path is only ever set in code or the environment, never through the admin form
        check_public_url(self.source)
        response = self.http.get(self.source, timeout=TIMEOUT, headers={"User-Agent": "ZaldiFeedReader/1.0"})
        response.raise_for_status()
        if len(response.content) > MAX_BYTES:
            raise ValidationError("the feed is too large")
        return response.content.decode("utf-8-sig", errors="replace")

    def _cards(self) -> list[dict]:
        if self._cached and self.clock() - self._cached[0] < TTL:
            return self._cached[1]
        try:
            cards, skipped = parse(self._load(), self.currency, self.label)
        except Exception as exc:
            if self._cached:
                return self._cached[1]  # a stale copy beats failing the shopper's question
            raise ValidationError("the product feed could not be read") from exc
        self._cached = (self.clock(), cards, skipped)
        return cards

    @property
    def skipped_rows(self) -> int:
        self._cards()
        return self._cached[2] if self._cached else 0
