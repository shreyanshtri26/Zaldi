"""GET /api/site-config: public storefront text and quick-action cards."""
from flask import Blueprint, jsonify

from zaldi.services import site_config

bp = Blueprint("site", __name__)


@bp.get("/site-config")
def get_site_config():
    return jsonify(site_config.get_site_config())


@bp.get("/health")
def health():
    return jsonify(status="ok")
