"""Tools the agent may call, built from what the connected store supports.

``session_id`` is bound here, on the server: the model never sees it and cannot act on another shopper's cart. Every tool
returns plain data and turns a store ``ValidationError`` (out of stock, unknown product) into ``{"error": ...}`` so the model
can recover instead of crashing the run. Each call is recorded in ``Run.steps`` for the chat and the admin trace.
"""
import time

from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from zaldi.connectors.base import CART, CHECKOUT, POLICIES, PREFERENCES, SEARCH, StoreConnector
from zaldi.errors import ValidationError

POLICY_EXCERPT_LIMIT = 600
MAX_CARDS = 6


class Run:
    """Everything one agent run produced: the trace plus what the UI should render (cards, cart, next action)."""

    def __init__(self) -> None:
        self.steps: list[dict] = []
        self.products: dict[int, dict] = {}
        self.cart: dict | None = None
        self.action: str | None = None
        self.ask: dict | None = None  # a question for the shopper, with tappable answers


class SearchArgs(BaseModel):
    query: str = Field(description="What the shopper wants, in their own words, e.g. 'red cotton saree'")
    max_price: int | None = Field(default=None, description="Upper budget in rupees, if the shopper gave one")
    min_price: int | None = Field(default=None, description="Lower budget in rupees, if any")
    category: str | None = Field(default=None, description="Exact category name from the store, if the shopper named one")
    sort: Literal["price_asc", "price_desc", "rating"] | None = Field(default=None, description="Ordering the shopper asked for: cheapest, most expensive, top rated")


class ProductArgs(BaseModel):
    product_id: int | str = Field(description="Id of a product returned by search_products")


class PolicyArgs(BaseModel):
    query: str = Field(description="The policy question, e.g. 'return window for sarees'")


class AddArgs(BaseModel):
    product_id: int = Field(description="Id of a product returned by search_products in this conversation")
    quantity: int = Field(default=1, ge=1, le=10)


class PreferenceArgs(BaseModel):
    size: str | None = Field(default=None, description="Usual size, e.g. 'M' or '40'")
    max_price: int | None = Field(default=None, description="Usual budget ceiling in rupees")
    gender: str | None = Field(default=None, description="Who they shop for: Men, Women, Boys or Girls")
    brand: str | None = Field(default=None, description="A brand they only want")


class AskArgs(BaseModel):
    question: str = Field(description="One short question, e.g. 'Which size do you wear?'")
    options: list[str] = Field(default_factory=list, description="Up to 4 short answers the shopper can tap, e.g. ['S', 'M', 'L']")


class NoArgs(BaseModel):
    pass


def _slim(card: dict) -> dict:
    """What the model needs to compare products; images and long text stay out."""
    return {"id": card["id"], "name": card["product_name"], "brand": card["brand"], "category": card["category"],
            "color": card["color"], "sizes": card["size"], "material": card["material"], "price": card["price"], "currency": card.get("currency", "INR"),
            "rating": card.get("rating"), "reviews": card.get("rating_count"), "in_stock": "unknown" if card["stock_quantity"] is None else card["stock_quantity"], "about": card["description"]}


def build_tools(connector: StoreConnector, session_id: str, run: Run) -> list[StructuredTool]:
    caps = connector.capabilities

    def traced(name: str, summarize):
        """Wrap a tool body: time it, record the step, and return errors as data."""
        def wrap(fn):
            def call(**kwargs):
                started = time.perf_counter()
                try:
                    out = fn(**kwargs)
                except ValidationError as exc:
                    out = {"error": str(exc)}
                run.steps.append({"tool": name, "summary": out["error"] if "error" in out else summarize(out, kwargs),
                                  "ok": "error" not in out, "ms": round((time.perf_counter() - started) * 1000)})
                return out
            return call
        return wrap

    def remember(card: dict) -> None:
        if len(run.products) < MAX_CARDS or card["id"] in run.products:
            run.products[card["id"]] = card

    def name_of(product_id: int) -> str:
        return run.products.get(product_id, {}).get("product_name") or f"product {product_id}"

    tools: list[StructuredTool] = []

    def add(fn, name: str, description: str, schema: type[BaseModel]) -> None:
        tools.append(StructuredTool.from_function(func=fn, name=name, description=description, args_schema=schema))

    @traced("ask_shopper", lambda out, a: f"Asked: {a['question']}")
    def ask_shopper(question: str, options: list[str] | None = None) -> dict:
        run.ask = {"question": question.strip()[:200], "options": [o.strip()[:40] for o in (options or []) if o.strip()][:4]}
        return {"status": "the question is shown to the shopper; stop here and wait for their answer"}

    add(ask_shopper, "ask_shopper",
        "Ask the shopper for something you need before you can help well (size, colour, budget, occasion, which product). "
        "They can tap an answer. Use it instead of guessing, then stop.", AskArgs)

    if SEARCH in caps:
        @traced("search_products", lambda out, a: f"Found {len(out['products'])} products for \"{a['query']}\""
                + (f" (relaxed: {', '.join(out['relaxed'])})" if out["relaxed"] else ""))
        def search_products(query: str, max_price: int | None = None, min_price: int | None = None, category: str | None = None, sort: str | None = None) -> dict:
            found = connector.search_products(session_id, query, {"max_price": max_price, "min_price": min_price, "category": category, "sort": sort})
            for card in found["products"]:
                remember(card)
            return {"products": [_slim(c) for c in found["products"]], "relaxed": found["relaxed"]}

        @traced("get_product", lambda out, a: f"Looked up {out.get('name', 'a product')}")
        def get_product(product_id: int | str) -> dict:
            card = connector.get_product(product_id)
            if card is None:
                raise ValidationError("that product does not exist")
            remember(card)
            return _slim(card)

        add(search_products, "search_products", "Search the store catalogue. Use for any request about products, prices or availability.", SearchArgs)
        add(get_product, "get_product", "Get the current details and stock of one product by id.", ProductArgs)

    if POLICIES in caps:
        @traced("search_policies", lambda out, a: f"Read {len(out['excerpts'])} excerpts from {', '.join(out['sources']) or 'no policy'}")
        def search_policies(query: str) -> dict:
            excerpts = [p[:POLICY_EXCERPT_LIMIT] for p in connector.search_policies(query)]
            # each excerpt starts with its section title: that is the citation the agent can quote
            return {"excerpts": excerpts, "sources": sorted({e.split("\n", 1)[0] for e in excerpts})}

        add(search_policies, "search_policies", "Look up store policies: returns, shipping, payment, COD, sizing, care, coupons.", PolicyArgs)

    if CART in caps:
        @traced("view_cart", lambda out, a: f"Cart has {len(out['items'])} items")
        def view_cart() -> dict:
            run.cart = connector.cart_view(session_id)
            return run.cart

        @traced("add_to_cart", lambda out, a: f"Added {name_of(a['product_id'])} to the cart")
        def add_to_cart(product_id: int, quantity: int = 1) -> dict:
            run.cart = connector.cart_add(session_id, product_id, quantity)
            return run.cart

        @traced("remove_from_cart", lambda out, a: f"Removed {name_of(a['product_id'])} from the cart")
        def remove_from_cart(product_id: int | str) -> dict:
            run.cart = connector.cart_remove(session_id, product_id)
            return run.cart

        add(view_cart, "view_cart", "Show what is in the shopper's cart with totals.", NoArgs)
        add(add_to_cart, "add_to_cart", "Add a product to the cart. Checks stock; may return an error to explain.", AddArgs)
        add(remove_from_cart, "remove_from_cart", "Remove a product from the cart.", ProductArgs)

    if PREFERENCES in caps:
        @traced("remember_preference", lambda out, a: "Saved " + ", ".join(f"{k} {v}" for k, v in a.items() if v not in (None, "")))
        def remember_preference(size: str | None = None, max_price: int | None = None, gender: str | None = None, brand: str | None = None) -> dict:
            return connector.save_preference(session_id, {"size": size, "max_price": max_price, "gender": gender, "brand": brand})

        add(remember_preference, "remember_preference",
            "Save a lasting preference the shopper states about themselves ('I wear M', 'my budget is 3000'). Never guess one.", PreferenceArgs)

    if CHECKOUT in caps:
        @traced("start_checkout", lambda out, a: "Prepared checkout for the shopper to confirm")
        def start_checkout() -> dict:
            out = connector.start_checkout(session_id)
            if "error" in out:
                raise ValidationError(out["error"])
            run.cart, run.action = out.get("cart"), out.get("action")
            return {"status": "waiting for the shopper to enter delivery details and confirm", "cart": out.get("cart")}

        add(start_checkout, "start_checkout", "Begin checkout once the shopper wants to order. They finish in a secure form; nothing is bought until they confirm.", NoArgs)

    return tools
