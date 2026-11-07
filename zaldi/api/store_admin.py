"""Which store a request is for (``X-Store`` header) and the endpoints that create and manage stores (server admin only)."""
from flask import Blueprint, g, jsonify, request

from zaldi import stores
from zaldi.api.auth import admin_required, server_admin_required
from zaldi.api.ratelimit import rate_limited
from zaldi.services import accounts
from zaldi.errors import ValidationError

bp = Blueprint("store_admin", __name__, url_prefix="/admin")


def select_store() -> None:
    """Before every API request: pick the store named by the header (default if none) and refuse an unknown one."""
    slug = (request.headers.get("X-Store") or stores.DEFAULT).strip().lower()
    if slug != stores.DEFAULT and not stores.SLUG.fullmatch(slug):
        raise ValidationError("unknown store")
    if not stores.exists(slug):
        raise ValidationError("unknown store")
    g.store_token = stores.current.set(slug)


def release_store(exc=None) -> None:
    token = g.pop("store_token", None)
    if token is not None:
        stores.current.reset(token)


@bp.get("/stores")
@server_admin_required
def list_stores():
    return jsonify(stores=stores.list_stores())


@bp.post("/stores")
@server_admin_required
def create_store():
    body = request.get_json(silent=True) or {}
    return jsonify(stores.create_store(body.get("slug", ""), body.get("name", ""))), 201


@bp.put("/stores/<slug>")
@server_admin_required
def update_store(slug):
    body = request.get_json(silent=True) or {}
    return jsonify(stores.set_status(slug, body.get("status", "")))


@bp.delete("/stores/<slug>")
@server_admin_required
def delete_store(slug):
    if (request.get_json(silent=True) or {}).get("confirm") != slug:
        raise ValidationError("Type the store id to confirm. Deleting a store erases all of its data.")
    stores.delete_store(slug)
    return "", 204


@bp.get("/stores/<slug>/accounts")
@server_admin_required
def list_accounts(slug):
    return jsonify(accounts=accounts.list_accounts(slug))


@bp.post("/stores/<slug>/accounts")
@server_admin_required
def create_account(slug):
    body = request.get_json(silent=True) or {}
    return jsonify(accounts.create_account(body.get("email", ""), body.get("password", ""), slug, body.get("role", "owner"))), 201


@bp.post("/account-login")
@rate_limited("RATE_LIMIT_LOGIN")
def account_login():
    """Step one. Either the signed-in token, or ``needs_two_step`` and a short-lived challenge to answer with a code."""
    body = request.get_json(silent=True) or {}
    return jsonify(accounts.begin_login(body.get("email", ""), body.get("password", "")))


@bp.post("/account-login/two-step")
@rate_limited("RATE_LIMIT_LOGIN")
def account_login_two_step():
    body = request.get_json(silent=True) or {}
    return jsonify(accounts.finish_login(body.get("challenge", ""), body.get("code", "")))


@bp.post("/forgot-password")
@rate_limited("RATE_LIMIT_LOGIN")
def forgot_password():
    """Ask for a reset link by email. The answer is the same whether or not the account exists."""
    return jsonify(accounts.forgot_password((request.get_json(silent=True) or {}).get("email", ""), request.host_url))


@bp.post("/password-reset")
@rate_limited("RATE_LIMIT_LOGIN")
def password_reset():
    body = request.get_json(silent=True) or {}
    return jsonify(accounts.reset_password(body.get("token", ""), body.get("new", "")))


@bp.delete("/stores/<slug>/accounts/<email>")
@server_admin_required
def delete_account(slug, email):
    accounts.delete_account(slug, email)
    return "", 204


@bp.put("/stores/<slug>/accounts/<email>")
@server_admin_required
def update_account(slug, email):
    return jsonify(accounts.set_role(slug, email, (request.get_json(silent=True) or {}).get("role", "")))


@bp.post("/stores/<slug>/accounts/<email>/reset-link")
@server_admin_required
def account_reset_link(slug, email):
    """A one-hour, single-use link the server admin gives to the owner (no email needed)."""
    accounts._account_in(slug, email)
    token = accounts.create_reset(email)
    return jsonify(link=f"{request.host_url.rstrip('/')}/admin?reset={token}", expires_in=accounts.RESET_TTL)


@bp.post("/stores/<slug>/accounts/<email>/two-step/disable")
@server_admin_required
def account_two_step_off(slug, email):
    return jsonify(accounts.admin_turn_off_two_step(slug, email))


signup_bp = Blueprint("signup", __name__)


@signup_bp.post("/signup")
@rate_limited("RATE_LIMIT_LOGIN")
def signup():
    body = request.get_json(silent=True) or {}
    return jsonify(accounts.signup(body.get("email", ""), body.get("password", ""), body.get("store", ""), body.get("name", ""))), 201


@bp.get("/embed")
@admin_required
def embed_info():
    """What the owner pastes into their website, plus the websites currently allowed to show the assistant."""
    from zaldi.services import site_config

    host = request.host_url.rstrip("/")
    slug = stores.slug()
    store_attr = "" if slug == stores.DEFAULT else f' data-store="{slug}"'
    origins = [o.strip() for o in site_config.get_settings()["embed_origins"].split(",") if o.strip()]
    return jsonify(store=slug, host=host, allowed_origins=origins, snippet=f'<script src="{host}/widget.js"{store_attr} async></script>',
                   ready=bool(origins) or slug == stores.DEFAULT)
