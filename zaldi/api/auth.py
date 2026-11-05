"""Admin authentication: a shared token sent in the ``X-Admin-Token`` header."""
import hmac
from functools import wraps

from flask import jsonify, request

from zaldi import config

HEADER = "X-Admin-Token"


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not config.ADMIN_TOKEN:
            return jsonify(error="ADMIN_TOKEN is not configured on the server"), 503
        if not hmac.compare_digest(request.headers.get(HEADER, ""), config.ADMIN_TOKEN):
            return jsonify(error="invalid admin token"), 401
        return view(*args, **kwargs)

    return wrapper
