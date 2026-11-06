"""Admin authentication.

Two kinds of credential travel in the ``X-Admin-Token`` header:
* the server admin's ``ADMIN_TOKEN``: may do everything, in any store, including creating stores and accounts;
* a store owner's signed token (from an account login): limited to that account's own store, and a ``viewer`` may only read.
"""
import hmac
from functools import wraps

from flask import g, jsonify, request

from zaldi import config, stores

HEADER = "X-Admin-Token"
READ_ONLY = ("GET", "HEAD", "OPTIONS")


def _who() -> tuple[str, dict | None]:
    """``("server", None)``, ``("account", account)`` or ``("none", None)`` for the credential on this request."""
    given = request.headers.get(HEADER, "")
    if config.ADMIN_TOKEN and hmac.compare_digest(given, config.ADMIN_TOKEN):
        return "server", None
    if given:
        from zaldi.services import accounts

        account = accounts.verify_token(given)
        if account:
            return "account", account
    return "none", None


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        kind, account = _who()
        if kind == "none":
            if not config.ADMIN_TOKEN:
                return jsonify(error="ADMIN_TOKEN is not configured on the server"), 503
            return jsonify(error="invalid admin token"), 401
        if kind == "account":
            if account["store"] != stores.slug():
                return jsonify(error="this account manages a different store"), 403
            if account["role"] == "viewer" and request.method not in READ_ONLY:
                return jsonify(error="viewers can look but not change anything"), 403
            g.account = account
        return view(*args, **kwargs)

    return wrapper


def server_admin_required(view):
    """Only the server admin: creating stores and accounts is not something a store owner may do."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        kind, _ = _who()
        if kind != "server":
            if not config.ADMIN_TOKEN:
                return jsonify(error="ADMIN_TOKEN is not configured on the server"), 503
            return jsonify(error="only the server admin can do this"), 401 if kind == "none" else 403
        return view(*args, **kwargs)

    return wrapper
