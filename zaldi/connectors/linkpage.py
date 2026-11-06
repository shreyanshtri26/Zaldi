"""Link connector: the admin pastes product page links; we read the standard product data each page publishes for search engines
(schema.org JSON-LD, falling back to Open Graph tags). No API is needed, which makes this the way in for any shop.

Rules: only public http(s) pages, ``robots.txt`` is respected, at most ``MAX_LINKS`` pages, and Amazon/Flipkart pages are refused (their
terms forbid reading product pages; use their affiliate connectors instead).
"""
import hashlib
import json
import time
import urllib.parse
import urllib.robotparser
from html.parser import HTMLParser

import requests

from zaldi.connectors.catalogue import CatalogueStore, make_card
from zaldi.connectors.netguard import check_public_url
from zaldi.errors import ValidationError

MAX_LINKS = 50
TTL = 3600
TIMEOUT = 12
USER_AGENT = "ZaldiBot/1.0 (+product-reader)"
FORBIDDEN_HOSTS = ("amazon.", "flipkart.", "amzn.", "fkrt.")


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ld, self.meta, self._in_ld = [], {}, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_ld = True
            self.ld.append("")
        elif tag == "meta":
            key = a.get("property") or a.get("name")
            if key and a.get("content"):
                self.meta[key.lower()] = a["content"]

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_ld = False

    def handle_data(self, data):
        if self._in_ld and self.ld:
            self.ld[-1] += data


def _walk(node):
    """Every dict inside parsed JSON-LD, including ``@graph`` members and list items."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _first(value):
    return value[0] if isinstance(value, list) and value else value


def parse_page(html: str, url: str, source: str = "") -> dict | None:
    """A card from one product page, or ``None`` when the page publishes no product with a name and a price."""
    page = _Page()
    page.feed(html[:2_000_000])
    pid = hashlib.sha1(url.encode()).hexdigest()[:12]
    for block in page.ld:
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for node in _walk(data):
            kinds = node.get("@type")
            if "Product" not in (kinds if isinstance(kinds, list) else [kinds]):
                continue
            offer = _first(node.get("offers")) or {}
            offer = _first(offer.get("offers")) if isinstance(offer, dict) and "offers" in offer else offer
            image = _first(node.get("image"))
            brand = node.get("brand")
            rating = node.get("aggregateRating") or {}
            card = make_card(pid, node.get("name"), (offer or {}).get("price") or (offer or {}).get("lowPrice"),
                             (offer or {}).get("priceCurrency", "INR"), category=node.get("category") or "",
                             brand=brand.get("name") if isinstance(brand, dict) else brand or "",
                             image=image.get("url") if isinstance(image, dict) else image, url=url, description=node.get("description") or "",
                             rating=_num(rating.get("ratingValue")), rating_count=_num(rating.get("reviewCount") or rating.get("ratingCount")),
                             in_stock=False if "OutOfStock" in str((offer or {}).get("availability", "")) else None, source=source)
            if card:
                return card
    m = page.meta
    return make_card(pid, m.get("og:title"), m.get("product:price:amount") or m.get("og:price:amount"),
                     m.get("product:price:currency") or m.get("og:price:currency") or "INR", image=m.get("og:image"), url=url,
                     description=m.get("og:description") or "", source=source)


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class LinkStore(CatalogueStore):
    name = "links"

    def __init__(self, links: str | list[str], label: str = "", http=requests, clock=time.monotonic, check_url=check_public_url) -> None:
        raw = links.split() if isinstance(links, str) else links
        self.links = [u for u in dict.fromkeys(x.strip() for x in raw) if u][:MAX_LINKS]
        if not self.links:
            raise ValueError("paste at least one product link")
        for url in self.links:
            host = urllib.parse.urlparse(url).netloc.lower()
            if any(bad in host for bad in FORBIDDEN_HOSTS):
                raise ValueError("Amazon and Flipkart pages cannot be read here: use their affiliate connectors")
        self.label, self.http, self.clock, self.check_url = label, http, clock, check_url
        self._cached: tuple[float, list[dict], list[str]] | None = None
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _allowed(self, url: str) -> bool:
        parts = urllib.parse.urlparse(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                response = self.http.get(f"{base}/robots.txt", timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
                rp.parse(response.text.splitlines() if response.status_code == 200 else [])
            except Exception:
                rp.parse([])
            self._robots[base] = rp
        return self._robots[base].can_fetch(USER_AGENT, url)

    def _read(self) -> tuple[list[dict], list[str]]:
        cards, problems = [], []
        for url in self.links:
            try:
                self.check_url(url)
                if not self._allowed(url):
                    problems.append(f"{url}: the site's robots.txt asks readers to stay away")
                    continue
                response = self.http.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
                response.raise_for_status()
                card = parse_page(response.text, url, self.label)
                if card:
                    cards.append(card)
                else:
                    problems.append(f"{url}: no product name and price found on the page")
            except Exception as exc:
                problems.append(f"{url}: {exc if isinstance(exc, ValidationError) else 'could not be read'}")
        return cards, problems

    def _cards(self) -> list[dict]:
        if self._cached and self.clock() - self._cached[0] < TTL:
            return self._cached[1]
        cards, problems = self._read()
        if not cards and self._cached:
            return self._cached[1]
        self._cached = (self.clock(), cards, problems)
        return cards

    @property
    def problems(self) -> list[str]:
        self._cards()
        return self._cached[2] if self._cached else []
