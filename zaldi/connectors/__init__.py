from zaldi.connectors.base import StoreConnector


CONNECTOR_NAMES = ("local", "woocommerce", "shopify", "escuelajs", "feed", "rest", "links", "amazon", "flipkart")


def build_connector(values: dict) -> StoreConnector:
    """Make the connector described by ``values`` (see ``zaldi.services.store_settings``). A misconfigured store fails loudly."""
    kind = (values.get("connector") or "local").strip().lower()
    if kind == "woocommerce":
        from zaldi.connectors.woocommerce import WooStore

        return WooStore(values["woocommerce_url"], values["woocommerce_key"], values["woocommerce_secret"])
    if kind == "shopify":
        from zaldi.connectors.shopify import ShopifyStore

        return ShopifyStore(values["shopify_domain"], values["shopify_token"], values["shopify_version"])
    if kind == "escuelajs":
        from zaldi.connectors.escuelajs import EscuelaStore

        return EscuelaStore(values["escuelajs_url"])
    if kind == "feed":
        from zaldi.connectors.feed import FeedStore

        return FeedStore(values["feed_url"], label=values.get("feed_label", ""))
    if kind == "rest":
        from zaldi.connectors.rest import RestStore

        return RestStore(values["rest_config"])
    if kind == "links":
        from zaldi.connectors.linkpage import LinkStore

        return LinkStore(values["link_urls"], label=values.get("feed_label", ""))
    if kind == "amazon":
        from zaldi.connectors.amazon import AmazonStore

        return AmazonStore(values["amazon_credential_id"], values["amazon_credential_secret"], values["amazon_partner_tag"],
                           values["amazon_token_url"], values.get("amazon_marketplace") or "www.amazon.in")
    if kind == "flipkart":
        from zaldi.connectors.flipkart import FlipkartStore

        return FlipkartStore(values["flipkart_affiliate_id"], values["flipkart_token"])
    if kind != "local":
        raise ValueError(f"unknown store connector: {kind!r} (use one of {', '.join(CONNECTOR_NAMES)})")
    from zaldi.connectors.local import LocalStore

    return LocalStore()


_connectors: dict[str, StoreConnector] = {}


def get_connector() -> StoreConnector:
    """The connector for the current store: its admin settings first, then the environment. Cleared whenever the settings change."""
    from zaldi import stores
    from zaldi.services import store_settings

    key = stores.slug()
    if key not in _connectors:
        _connectors[key] = build_connector(store_settings.effective())
    return _connectors[key]


def _clear() -> None:
    from zaldi import stores

    _connectors.pop(stores.slug(), None)


get_connector.cache_clear = _clear  # kept so callers can reset the current store's connector
