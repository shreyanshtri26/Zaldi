"""CRUD endpoints for CMS content. Reads are public (the storefront needs them); writes need the admin token."""
from flask import Blueprint, jsonify, request

from zaldi.api.auth import admin_required
from zaldi.db import content_repo


def make_content_blueprint(table: str) -> Blueprint:
    """Build ``/<table>`` routes: list, create, get, update, delete."""
    bp = Blueprint(table, __name__, url_prefix=f"/{table}")

    def not_found():
        return jsonify(error="not found"), 404

    @bp.get("")
    def list_items():
        return jsonify(content_repo.list_rows(table, request.args.get("q", ""), request.args.get("category", "")))

    @bp.post("")
    @admin_required
    def create_item():
        return jsonify(content_repo.create_row(table, request.get_json(silent=True) or {})), 201

    @bp.get("/<int:item_id>")
    def get_item(item_id: int):
        row = content_repo.get_row(table, item_id)
        return jsonify(row) if row else not_found()

    @bp.put("/<int:item_id>")
    @admin_required
    def update_item(item_id: int):
        row = content_repo.update_row(table, item_id, request.get_json(silent=True) or {})
        return jsonify(row) if row else not_found()

    @bp.delete("/<int:item_id>")
    @admin_required
    def delete_item(item_id: int):
        return ("", 204) if content_repo.delete_row(table, item_id) else not_found()

    return bp
