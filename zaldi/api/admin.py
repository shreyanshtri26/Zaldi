"""Admin-only endpoints: token check, dashboard data, site settings and assistant prompts."""
from flask import Blueprint, jsonify, request

from zaldi.api.auth import admin_required
from zaldi.api.ratelimit import rate_limited
from zaldi.db import chat_log_repo
from zaldi.services import prompt_service, site_config

bp = Blueprint("admin", __name__, url_prefix="/admin")
RECENT_CHATS = 20


@bp.post("/login")
@rate_limited("RATE_LIMIT_LOGIN")
@admin_required
def login():
    return jsonify(ok=True)


@bp.get("/stats")
@admin_required
def get_stats():
    return jsonify(chat_log_repo.stats() | {"recent_chats": chat_log_repo.recent_logs(RECENT_CHATS)})


@bp.get("/settings")
@admin_required
def get_settings():
    return jsonify(settings=site_config.get_settings(), defaults=site_config.defaults())


@bp.put("/settings")
@admin_required
def put_settings():
    changes = request.get_json(silent=True) or {}
    return jsonify(settings=site_config.update_settings(changes), defaults=site_config.defaults())


@bp.get("/prompts")
@admin_required
def get_prompts():
    return jsonify(prompt_service.list_prompts())


@bp.put("/prompts/<name>")
@admin_required
def put_prompt(name: str):
    return jsonify(prompt_service.update_prompt(name, (request.get_json(silent=True) or {}).get("content")))


@bp.delete("/prompts/<name>")
@admin_required
def delete_prompt(name: str):
    return jsonify(prompt_service.reset_prompt(name))
