"""Check the Amazon and Flipkart connectors (and the feed and link readers).

    python scripts/check_marketplaces.py            # recorded sample responses, no keys needed
    python scripts/check_marketplaces.py --live     # your real keys from the environment / .env: prints the true response shape
    python scripts/check_marketplaces.py --live --record   # also saves that shape (field names only) to evals/results/marketplace_shapes.json

Live mode reads AMAZON_CREDENTIAL_ID, AMAZON_CREDENTIAL_SECRET, AMAZON_PARTNER_TAG (and AMAZON_MARKETPLACE, default www.amazon.in; the
token address is chosen from the marketplace's region unless AMAZON_TOKEN_URL is set) and FLIPKART_AFFILIATE_ID, FLIPKART_TOKEN. It sends one search for "kurta" per marketplace, prints the response's top-level keys and the
first item's keys (never your keys or tokens), then runs the connector on it and the same contract the tests use. If a field is
missing, the printed shape shows which name the marketplace really uses; fix it in zaldi/connectors/amazon.py or flipkart.py.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ALLOW_PRIVATE_STORE_URLS", "1")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from tests.fakes import FIXTURES, FakeHttp, check_connector, fixture  # noqa: E402
from zaldi.connectors.amazon import AmazonStore  # noqa: E402
from zaldi.connectors.feed import FeedStore  # noqa: E402
from zaldi.connectors.flipkart import FlipkartStore  # noqa: E402
from zaldi.connectors.linkpage import LinkStore  # noqa: E402


def shape(data, depth=0):
    """Field names only, never values: safe to paste into a bug report."""
    if isinstance(data, dict):
        return {k: shape(v, depth + 1) if depth < 3 else "..." for k, v in data.items()}
    return [shape(data[0], depth + 1)] if isinstance(data, list) and data else type(data).__name__


def run(label, store, query="kurta"):
    try:
        cards = check_connector(store, query=query)
        print(f"  PASS  {label}: {len(cards)} products, e.g. {cards[0]['product_name']!r} {cards[0]['currency']} {cards[0]['price']}")
        return True
    except Exception as exc:
        print(f"  FAIL  {label}: {type(exc).__name__}: {str(exc)[:200]}")
        return False


def offline() -> bool:
    # No token address is given: it is chosen from the marketplace (India -> the EU token endpoint), as it will be with real keys.
    amazon = AmazonStore("id", "secret", "tag-21", http=FakeHttp({"https://api.amazon.co.uk/auth/o2/token": {"access_token": "t", "expires_in": 3600},
                                                                  "https://creatorsapi.amazon/catalog/v1/searchItems": fixture("amazon_search.json")}))
    flipkart = FlipkartStore("aff", "tok", http=FakeHttp({"https://affiliate-api.flipkart.net/affiliate/1.0/search.json": fixture("flipkart_search.json")}))
    feed = FeedStore(str(FIXTURES / "feed.csv"))
    links = LinkStore("https://shop.test/saree", http=FakeHttp({"https://shop.test/robots.txt": ("", 404), "https://shop.test/saree": fixture("product_page.html")}),
                      check_url=lambda u: u)
    print("Recorded responses:")
    ok = all([run("Amazon", amazon), run("Flipkart", flipkart), run("Product feed", feed), run("Link pages", links, "saree")])
    # The same connectors, over real HTTP with the real requests library, against a local server that speaks the documented protocols.
    from tests.fakes import MarketplaceServer

    print("Real HTTP against a simulated marketplace (checks token request, bearer token, marketplace and affiliate headers, parameters):")
    with MarketplaceServer() as server:
        ok &= all([run("Amazon", server.amazon()), run("Flipkart", server.flipkart())])
        refused = _refused(server)
    return ok and refused


def _refused(server) -> bool:
    """Wrong credentials must give a clear message, not a crash."""
    from zaldi.errors import ValidationError

    good = True
    for label, store in (("Amazon with a wrong secret", server.amazon(secret="wrong")), ("Flipkart with a wrong token", server.flipkart(token="wrong"))):
        try:
            store.search_products("s", "kurta")
            print(f"  FAIL  {label}: no error")
            good = False
        except ValidationError as exc:
            print(f"  PASS  {label}: {exc}")
    return good


def live() -> bool:
    import requests

    ok, ran = True, False
    env = os.environ.get
    if env("AMAZON_CREDENTIAL_ID") and env("AMAZON_CREDENTIAL_SECRET") and env("AMAZON_PARTNER_TAG"):
        ran = True
        print("Amazon (live):")
        http = _Spy()
        store = AmazonStore(env("AMAZON_CREDENTIAL_ID"), env("AMAZON_CREDENTIAL_SECRET", ""), env("AMAZON_PARTNER_TAG", ""), env("AMAZON_TOKEN_URL", ""),
                            env("AMAZON_MARKETPLACE", "www.amazon.in"), http=http)
        print(f"  token address: {store.token_url.split('//')[1].split('/')[0]} (marketplace {store.marketplace})")
        ok &= _report("amazon", store, http)
    else:
        print("Amazon: skipped (set AMAZON_CREDENTIAL_ID, AMAZON_CREDENTIAL_SECRET, AMAZON_PARTNER_TAG)")
    if env("FLIPKART_AFFILIATE_ID") and env("FLIPKART_TOKEN"):
        ran = True
        print("Flipkart (live):")
        http = _Spy()
        ok &= _report("flipkart", FlipkartStore(env("FLIPKART_AFFILIATE_ID"), env("FLIPKART_TOKEN"), http=http), http)
    else:
        print("Flipkart: skipped (set FLIPKART_AFFILIATE_ID, FLIPKART_TOKEN)")
    return ok if ran else True


class _Spy:
    """Real ``requests`` that remembers the shape of each JSON answer."""

    def __init__(self):
        import requests

        self.shapes, self._r = [], requests

    def _wrap(self, response):
        try:
            if "token" not in response.url:
                self.shapes.append((response.status_code, shape(response.json())))
        except Exception:
            self.shapes.append((response.status_code, "not JSON"))
        return response

    def get(self, *a, **k):
        return self._wrap(self._r.get(*a, **k))

    def post(self, *a, **k):
        return self._wrap(self._r.post(*a, **k))


RECORDED: dict = {}


def _report(name, store, http) -> bool:
    ok = run("contract", store)
    for status, s in http.shapes[:2]:
        print(f"  response shape (HTTP {status}):", json.dumps(s, indent=1)[:1500])
    RECORDED[name] = [{"status": status, "shape": s} for status, s in http.shapes[:2]]
    return ok


if __name__ == "__main__":
    good = live() if "--live" in sys.argv else offline()
    if "--record" in sys.argv and RECORDED:
        target = ROOT / "evals" / "results" / "marketplace_shapes.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(RECORDED, indent=1), encoding="utf-8")  # field names and types only: no keys, no prices, no product text
        print(f"Saved the response shapes to {target.relative_to(ROOT)}")
    print("\nAll checks passed." if good else "\nSome checks failed: see above.")
    sys.exit(0 if good else 1)
