from functools import lru_cache

from zaldi.connectors.base import StoreConnector


def build_connector(values: dict) -> StoreConnector:
    """Make the connector described by ``values`` (see ``zaldi.services.store_settings``). A misconfigured store fails loudly."""
    kind = (values.get("connector") or "local").strip().lower()
    if kind == "woocommerce":
        from zaldi.connectors.woocommerce import WooStore

        return WooStore(values["woocommerce_url"], values["woocommerce_key"], values["woocommerce_secret"])
    if kind == "shopify":
        from zaldi.connectors.shopify import ShopifyStore

        return ShopifyStore(values["shopify_domain"], values["shopify_token"], values["shopify_version"])
    if kind == "fakestore":
        from zaldi.connectors.fakestore import FakeStore

        return FakeStore(values["fakestore_url"])
    if kind != "local":
        raise ValueError(f"unknown store connector: {kind!r} (use local, woocommerce, shopify or fakestore)")
    from zaldi.connectors.local import LocalStore

    return LocalStore()


@lru_cache(maxsize=1)
def get_connector() -> StoreConnector:
    """The store the agent works against: admin settings first, then the environment. Cleared whenever the settings change."""
    from zaldi.services import store_settings

    return build_connector(store_settings.effective())
