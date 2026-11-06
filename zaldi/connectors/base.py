"""The seam between the agent and a store. The agent only ever talks to a ``StoreConnector``, so supporting another
platform (Shopify, WooCommerce, a marketplace affiliate feed, a CSV) means writing one new class, not touching the agent.

A connector declares what it can do in ``capabilities``; the agent is only given tools for those. A catalogue-only
marketplace connector, for example, has no ``cart`` or ``checkout`` and the agent simply hands the shopper a link.
"""
from typing import Protocol

# What a connector may support. Each capability unlocks the tools named beside it (see zaldi.agent.tools).
SEARCH = "search"        # search_products, get_product
POLICIES = "policies"    # search_policies
CART = "cart"            # view_cart, add_to_cart, remove_from_cart
PREFERENCES = "preferences"  # save_preference
CHECKOUT = "checkout"    # start_checkout (always ends in a human confirmation or a hand-off link, never a silent payment)


def safe_url(url: str | None) -> str | None:
    """Links from a store go into the page: only plain http(s) is allowed (never ``javascript:`` or ``data:``)."""
    return url if isinstance(url, str) and url.lower().startswith(("https://", "http://")) else None


class StoreConnector(Protocol):
    name: str
    capabilities: frozenset[str]

    def search_products(self, session_id: str, query: str, filters: dict | None = None, limit: int = 6) -> dict:
        """``{"products": [card, ...], "relaxed": [filters dropped to find matches]}``. ``filters`` may hold
        ``max_price``, ``min_price`` and ``category``; anything else is read from the query text."""

    def get_product(self, product_id: int) -> dict | None: ...

    def list_categories(self) -> list[dict]:
        """Optional. ``[{"name", "count", "group"}]`` for the home page; a store that cannot list them just omits this."""

    def search_policies(self, query: str, k: int = 3) -> list[str]: ...

    def cart_view(self, session_id: str) -> dict: ...

    def cart_add(self, session_id: str, product_id: int, quantity: int = 1) -> dict: ...

    def cart_remove(self, session_id: str, product_id: int) -> dict: ...

    def save_preference(self, session_id: str, changes: dict) -> dict:
        """Merge ``changes`` (size, max_price, gender, brand) into the shopper's saved preferences."""

    def start_checkout(self, session_id: str) -> dict:
        """``{"cart": ..., "action": "collect_address"}`` or a ``{"checkout_url": ...}`` hand-off."""
