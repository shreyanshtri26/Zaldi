# Connecting a shop

Zaldi talks to a shop only through a `StoreConnector` (`zaldi/connectors/base.py`). This page covers each connector, what shoppers can do
through it, and how to write a new one.

## 1. Choosing a path

| Your situation | Use | Shoppers can |
|---|---|---|
| New shop, nothing yet | **Built-in store** (`local`) | Search, cart, checkout, orders, returns |
| Shopify or WooCommerce | **Shopify** / **WooCommerce** | Search, compare, open the product on your store |
| Any site with a product list | **Product feed** (`feed`) or **Custom API** (`rest`) | Search, compare, open the product |
| Products listed elsewhere | **Amazon**, **Flipkart**, or **Product page links** (`links`) | Search, compare, open the original page |

Set it up in **Admin -> Content -> Store connection**: pick the kind, fill in the fields, press **Test connection**. Secrets are write-only.

## 2. Capability levels

The agent is given only the tools a connector supports, so it never offers what a shop cannot do.

| Level | Meaning | Connectors |
|---|---|---|
| `catalogue` | Search, compare, policy answers, open the product page | feed, rest, links, amazon, flipkart, shopify, woocommerce, escuelajs |
| `cart` | Also build a cart in the chat | local |
| `orders` | Also check orders and start returns (with confirmation) | local |

## 3. The connectors

### Built-in store (`local`)
Zaldi's own catalogue, cart, orders, returns and checkout. Add products by hand, in bulk, or with photos (Admin -> Products). The only
connector that supports the full level.

### Product feed (`feed`)
A public https link to a CSV, TSV or JSON list (a Google Merchant export works as it is). Columns are matched by synonym
(`title`/`name`, `sale_price`/`price`, `link`/`url`, `image_link`/`image`, `availability`...). Rows without a name, id or price are skipped
and counted. Fetched at most every 15 minutes; a stale copy is used if the link is down.

### Custom API (`rest`)
Any JSON search endpoint, described by a mapping the portal builds instead of code:

``` json
{"search_url": "https://shop.example/api/search?q={query}&limit={limit}",
 "product_url": "https://shop.example/api/products/{id}",
 "headers": {"Authorization": "Bearer ..."},
 "items_path": "data.items",
 "fields": {"id": "sku", "name": "title", "price": "pricing.sale", "currency": "pricing.currency",
            "image": "images.0", "url": "links.web", "category": "category.name", "brand": "brand"},
 "currency": "INR", "label": "My shop"}
```

Paths use dots and list positions (`images.0`). `id`, `name` and `price` are required.

### Product page links (`links`)
Paste up to 50 product page links. Zaldi reads the standard product data each page publishes for search engines (schema.org JSON-LD,
falling back to Open Graph tags). It respects `robots.txt`, reads only public pages, and **refuses Amazon and Flipkart pages** (their
terms forbid it): use their affiliate connectors.

### Amazon (`amazon`)
The Amazon **Creators API** (the successor to PA-API 5, retired in 2026). You need an Associates account: credential id and secret,
partner tag, marketplace (`www.amazon.in`) and the token address shown with your credentials. Cards link to Amazon with your tag and say
"from Amazon". Prices are cached at most 10 minutes.

### Flipkart (`flipkart`)
The **Flipkart Affiliate API**: affiliate tracking id and API token. Cards link to Flipkart and say "from Flipkart".

> **Status of Amazon and Flipkart.** Both are built from the providers' published documentation and tested against recorded sample
> responses, because no affiliate account was available. Neither provider publishes the full search response, so the parsers accept the
> spellings seen in the documentation. Check yours with `python scripts/check_marketplaces.py --live`, which prints the real response
> shape (never your keys).

### Shopify, WooCommerce, Platzi demo
Read-only product search; each card links to the store's own page, so no cart or payment data passes through Zaldi. `escuelajs` is the free
[Platzi Fake Store API](https://api.escuelajs.co/docs), for trying things out; its data is an open sandbox and can include junk.

## 4. The card format

Every connector returns products in one shape (`connectors/catalogue.py: make_card`):

`id`, `product_name`, `brand`, `category`, `color`, `size`, `material`, `price` (a number), `currency` (3 letters), `stock_quantity`
(`None` when the store does not say; that is not "in stock"), `image_url`, `buy_url` (http(s) only), `description` (at most 240 characters),
`rating`, `rating_count`, `catalogue_only`, `source`.

Rows without a name, id or usable price are dropped, never shown.

## 5. The Test checklist

`services/onboarding.py` runs: store answers, products found, prices valid, pictures present, buy links present, pages read, rows usable.
Each result says what happened in plain words and what to do. The first four decide whether a store can go live.

## 6. Safety of store addresses

Addresses typed into the portal must be public http(s) links: private, loopback and link-local addresses are refused
(`connectors/netguard.py`), so the portal cannot be used to reach the server's own network. Set `ALLOW_PRIVATE_STORE_URLS=1` on a
development machine to allow localhost.

## 7. Writing a connector

1. Create `zaldi/connectors/<name>.py` with a class that has `name`, `capabilities` (a frozenset from `connectors/base.py`),
   `search_products(session_id, query, filters, limit)` returning `{"products": [...], "relaxed": []}`, and `get_product(id)`.
   For a catalogue-only source, subclass `CatalogueStore` (implement `_cards()`) and reuse `make_card` and `rank`.
2. Register it in `connectors/__init__.py: build_connector` and `CONNECTOR_NAMES`.
3. Add its settings to `services/store_settings.py` (`FIELDS`, validation) and `config.py`.
4. Add form fields in `frontend/src/features/admin/content/StoreConnection.jsx`.
5. Test it with the shared contract: `from tests.fakes import check_connector` and a `FakeHttp` with recorded responses
   (`tests/test_new_connectors.py` has an example for each connector).
6. Never reach the network without `netguard.check_public_url`, never log a key, and cache reads.
