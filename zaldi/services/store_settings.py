"""Which store the assistant works against, editable in the admin instead of ``.env``.

Admin values are saved as ``store.*`` rows in the ``settings`` table and override the environment. Secrets (API keys) are
write-only: they are stored but never returned to the browser, and an empty value means "keep what is saved". The database is
protected by the admin token; for production prefer environment variables so secrets never sit in the database.
"""
import re

from zaldi import config
from zaldi.db import override_repo
from zaldi.errors import ValidationError

PREFIX = "store."
CONNECTORS = ("local", "woocommerce", "shopify", "escuelajs", "feed", "rest", "links", "amazon", "flipkart")
MAX_LENGTH = 200
LONG = {"rest_config": 4000, "link_urls": 6000}  # fields that hold a mapping or a list of links
# setting -> (config attribute holding the environment value, is it a secret)
FIELDS = {
    "connector": ("STORE_CONNECTOR", False),
    "woocommerce_url": ("WOOCOMMERCE_URL", False), "woocommerce_key": ("WOOCOMMERCE_KEY", True), "woocommerce_secret": ("WOOCOMMERCE_SECRET", True),
    "shopify_domain": ("SHOPIFY_DOMAIN", False), "shopify_token": ("SHOPIFY_STOREFRONT_TOKEN", True), "shopify_version": ("SHOPIFY_API_VERSION", False),
    "escuelajs_url": ("ESCUELAJS_URL", False),
    "feed_url": ("FEED_URL", False), "feed_label": ("FEED_LABEL", False), "rest_config": ("REST_CONFIG", True), "link_urls": ("LINK_URLS", False),
    "amazon_credential_id": ("AMAZON_CREDENTIAL_ID", True), "amazon_credential_secret": ("AMAZON_CREDENTIAL_SECRET", True),
    "amazon_partner_tag": ("AMAZON_PARTNER_TAG", False), "amazon_token_url": ("AMAZON_TOKEN_URL", False), "amazon_marketplace": ("AMAZON_MARKETPLACE", False),
    "flipkart_affiliate_id": ("FLIPKART_AFFILIATE_ID", False), "flipkart_token": ("FLIPKART_TOKEN", True),
}
SECRETS = {k for k, (_, secret) in FIELDS.items() if secret}


def _stored() -> dict[str, str]:
    try:
        return {k[len(PREFIX):]: v for k, v in override_repo.get_overrides("settings").items() if k.startswith(PREFIX)}
    except Exception:  # no database yet: fall back to the environment
        return {}


def effective() -> dict[str, str]:
    """The values in force: an admin override if there is one, otherwise the environment."""
    stored = _stored()
    return {key: stored.get(key) or getattr(config, attr) or "" for key, (attr, _) in FIELDS.items()}


def public_view() -> dict:
    """What the admin form shows. Secrets are reported only as set / not set."""
    values, stored = effective(), _stored()
    return {"connectors": CONNECTORS,
            "values": {k: v for k, v in values.items() if k not in SECRETS},
            "secrets_set": {k: bool(values[k]) for k in SECRETS},
            "overridden": sorted(stored)}


def _check(key: str, value: str) -> None:
    if len(value) > LONG.get(key, MAX_LENGTH):
        raise ValidationError(f"{key} is too long")
    if key == "connector" and value not in CONNECTORS:
        raise ValidationError(f"connector must be one of: {', '.join(CONNECTORS)}")
    if key == "rest_config":
        import json

        from zaldi.connectors.rest import validate

        try:
            validate(json.loads(value))
        except ValueError as exc:
            raise ValidationError(f"rest_config: {exc}") from None
    if key == "link_urls" and not all(u.startswith("https://") for u in value.split()):
        raise ValidationError("every product link must start with https://")
    if key in ("woocommerce_url", "escuelajs_url", "feed_url", "amazon_token_url") and not value.startswith("https://"):
        raise ValidationError(f"{key} must start with https://")
    if key == "shopify_domain" and not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", value, re.I):
        raise ValidationError("shopify_domain must look like your-store.myshopify.com")


def update(changes: dict) -> dict:
    for key, value in changes.items():
        if key not in FIELDS:
            raise ValidationError(f"unknown setting: {key}")
        if not isinstance(value, str):
            raise ValidationError(f"{key} must be text")
        if value.strip():
            _check(key, value.strip())
    for key, value in changes.items():
        value = value.strip()
        if value:
            override_repo.set_override("settings", PREFIX + key, value)
        elif key not in SECRETS:  # blank = back to the environment value; a blank secret just means "unchanged"
            override_repo.delete_override("settings", PREFIX + key)
    _reload()
    return public_view()


def reset() -> dict:
    for key in FIELDS:
        override_repo.delete_override("settings", PREFIX + key)
    _reload()
    return public_view()


def _reload() -> None:
    from zaldi.connectors import get_connector

    get_connector.cache_clear()  # the next chat uses the new settings


def test_connection() -> dict:
    """Try the configured store with one harmless search. Never echoes a key or URL back."""
    from zaldi.connectors import build_connector
    from zaldi.services import onboarding

    try:
        return onboarding.check(build_connector(effective()))
    except ValueError as exc:  # missing or malformed settings: safe to show, they name settings and never contain secrets
        return {"ok": False, "message": str(exc)}
    except ValidationError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception:
        return {"ok": False, "message": "Could not connect. Check the address and keys."}
test_connection.__test__ = False  # not a pytest test, despite the name
