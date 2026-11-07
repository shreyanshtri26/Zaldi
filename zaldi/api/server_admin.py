"""Server-wide settings (server admin only): the admin password, the database, and restarting. Plus password change for store owners."""
import os
import signal
import threading

from flask import Blueprint, g, jsonify, request

from zaldi.api.auth import admin_required, server_admin_required
from zaldi.errors import ValidationError
from zaldi.services import accounts, server_settings

bp = Blueprint("server_admin", __name__, url_prefix="/admin")


def _body() -> dict:
    return request.get_json(silent=True) or {}


@bp.get("/server")
@server_admin_required
def get_server():
    return jsonify(server_settings.status())


@bp.put("/server/password")
@server_admin_required
def put_password():
    return jsonify(server_settings.set_password(_body().get("current", ""), _body().get("new", "")))


@bp.delete("/server/password")
@server_admin_required
def delete_password():
    return jsonify(server_settings.clear_password(_body().get("current", "")))


@bp.post("/server/database/test")
@server_admin_required
def test_database():
    return jsonify(server_settings.test_database(_body().get("url", "")))


@bp.put("/server/database")
@server_admin_required
def put_database():
    return jsonify(server_settings.save_database(_body().get("url", "")))


@bp.delete("/server/database")
@server_admin_required
def delete_database():
    return jsonify(server_settings.clear_database())


@bp.post("/server/database/copy")
@server_admin_required
def copy_database():
    body = _body()
    replace = bool(body.get("replace"))
    if replace and body.get("confirm") != "REPLACE":
        raise ValidationError('Type REPLACE to confirm that the data in that database will be erased and replaced.')
    return jsonify(server_settings.copy_database(body.get("url", ""), replace))


@bp.post("/server/restart")
@server_admin_required
def restart():
    """Restart so a saved database address takes effect. Under gunicorn the master reloads every worker; otherwise the process exits and
    whatever supervises it (Render, Docker) starts it again. A development server simply stops."""
    if _body().get("confirm") != "RESTART":
        raise ValidationError("Type RESTART to confirm.")
    gunicorn = request.environ.get("SERVER_SOFTWARE", "").startswith("gunicorn") and hasattr(signal, "SIGHUP")

    def go():
        if gunicorn:
            os.kill(os.getppid(), signal.SIGHUP)
        else:
            os._exit(3)

    threading.Timer(1.0, go).start()  # after this response has been sent
    return jsonify(ok=True, message="Restarting. This page will work again in a few seconds."), 202


@bp.put("/account/password")
@admin_required
def put_account_password():
    """A store owner or viewer changes their own password. (The server admin uses /server/password.)"""
    account = g.get("account")
    if not account:
        raise ValidationError("Sign in with a store account to change its password. The server admin password is changed under Server.")
    return jsonify(accounts.change_password(account["email"], _body().get("current", ""), _body().get("new", "")))


def _own_account() -> dict:
    account = g.get("account")
    if not account:
        raise ValidationError("Sign in with a store account to use this. The server admin signs in with the admin password.")
    return account


@bp.get("/account/two-step")
@admin_required
def two_step_status():
    return jsonify(accounts.two_step_status(_own_account()["email"]))


@bp.post("/account/two-step/setup")
@admin_required
def two_step_setup():
    return jsonify(accounts.begin_two_step(_own_account()["email"], _body().get("password", "")))


@bp.post("/account/two-step/enable")
@admin_required
def two_step_enable():
    return jsonify(accounts.confirm_two_step(_own_account()["email"], _body().get("code", "")))


@bp.post("/account/two-step/disable")
@admin_required
def two_step_disable():
    return jsonify(accounts.disable_two_step(_own_account()["email"], _body().get("password", ""), _body().get("code", "")))
