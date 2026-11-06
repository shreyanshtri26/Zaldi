"""Categories for the home page, from whichever store is connected, shaped by the admin's display settings."""
import logging

from zaldi.connectors import get_connector
from zaldi.errors import ValidationError
from zaldi.services import site_config

log = logging.getLogger(__name__)
MAX_SHOWN = 60


def home_categories() -> dict:
    """``{"categories": [{name, count, group}], "shown": n, "store": name}``; empty when the store cannot list categories."""
    settings = site_config.get_settings()
    hidden = {h.strip().lower() for h in settings["home_categories_hidden"].split(",") if h.strip()}
    try:
        store = get_connector()
        lister = getattr(store, "list_categories", None)
        found = lister() if lister else []
    except (ValidationError, ValueError):
        log.warning("categories unavailable for the connected store")
        store, found = None, []
    shown = max(1, min(MAX_SHOWN, int(settings["home_categories_max"])))
    return {"categories": [c for c in found if c["name"].lower() not in hidden], "shown": shown, "store": getattr(store, "name", "")}
