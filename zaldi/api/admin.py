"""Admin-only endpoints: token check, dashboard data, site settings and assistant prompts."""
from flask import Blueprint, jsonify, request

from zaldi.api.auth import admin_required
from zaldi.api.ratelimit import rate_limited
from zaldi.db import chat_log_repo
from zaldi.services import ai_key, prompt_service, site_config, store_settings

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


@bp.get("/store")
@admin_required
def get_store():
    return jsonify(store_settings.public_view())


@bp.put("/store")
@admin_required
def put_store():
    return jsonify(store_settings.update(request.get_json(silent=True) or {}))


@bp.delete("/store")
@admin_required
def delete_store():
    return jsonify(store_settings.reset())


@bp.post("/store/test")
@admin_required
def test_store():
    return jsonify(store_settings.test_connection())


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


def _provider() -> str:
    """The provider a request is about: ``?provider=`` or the JSON body's ``provider`` (default Gemini, for the first version's callers)."""
    return request.args.get("provider") or (request.get_json(silent=True) or {}).get("provider") or "google"


@bp.get("/ai-key")
@admin_required
def get_ai_key():
    return jsonify(ai_key.status())


@bp.put("/ai-key")
@admin_required
def put_ai_key():
    body = request.get_json(silent=True) or {}
    return jsonify(ai_key.set_key(body.get("api_key") or body.get("google_api_key") or "", _provider()))


@bp.delete("/ai-key")
@admin_required
def delete_ai_key():
    return jsonify(ai_key.clear_key(_provider()))


@bp.post("/ai-key/test")
@admin_required
def test_ai_key():
    return jsonify(ai_key.test(request.args.get("provider") or (request.get_json(silent=True) or {}).get("provider")))


@bp.get("/ai-models")
@admin_required
def get_ai_models():
    provider = _provider()
    status = ai_key.provider_status(provider)
    return jsonify(ai_key.list_models(provider) | {"selected": status["model"], "is_default": status["model_is_default"], "default": status["default_model"]})


@bp.put("/ai-model")
@admin_required
def put_ai_model():
    return jsonify(ai_key.set_model((request.get_json(silent=True) or {}).get("model", ""), _provider()))


@bp.delete("/ai-model")
@admin_required
def delete_ai_model():
    return jsonify(ai_key.clear_model(_provider()))


@bp.put("/ai-provider")
@admin_required
def put_ai_provider():
    return jsonify(ai_key.set_provider(_provider()))


@bp.delete("/ai-provider")
@admin_required
def delete_ai_provider():
    return jsonify(ai_key.clear_provider())
