"""HTTP API: everything under ``/api`` (plus the demo storefront under ``/store-sim``)."""
from flask import Blueprint, Flask

from zaldi.api import admin, agents, chat, insights, server_admin, shop, site, store_admin, uploads
from zaldi.api.content import make_content_blueprint
from zaldi.api.errors import register_error_handlers
from zaldi.checkout.store_sim import bp as store_sim_bp

CONTENT_TABLES = ("products", "policies", "quick_actions")


def register_api(app: Flask) -> None:
    api = Blueprint("api", __name__, url_prefix="/api")
    for child in (chat.bp, insights.bp, server_admin.bp, store_admin.bp, store_admin.signup_bp, shop.bp, admin.bp, agents.bp, site.bp, uploads.bp, *(make_content_blueprint(t) for t in CONTENT_TABLES)):
        api.register_blueprint(child)
    api.before_request(store_admin.select_store)
    api.teardown_request(store_admin.release_store)
    app.register_blueprint(api)
    app.register_blueprint(uploads.files)
    app.register_blueprint(store_sim_bp)
    register_error_handlers(app)
