"""Feedback from shoppers (public) and the metrics page for admins."""
from flask import Blueprint, jsonify, request

from zaldi.api.auth import admin_required
from zaldi.api.ratelimit import rate_limited
from zaldi.errors import ValidationError
from zaldi.services import metrics

bp = Blueprint("insights", __name__)


@bp.post("/feedback")
@rate_limited("RATE_LIMIT_CHAT")
def post_feedback():
    body = request.get_json(silent=True) or {}
    try:
        chat_id, rating = int(body.get("chat_id")), int(body.get("rating"))
    except (TypeError, ValueError):
        raise ValidationError("chat_id and rating are required") from None
    metrics.record_feedback(chat_id, rating, str(body.get("comment") or ""))
    return jsonify(ok=True)


@bp.get("/admin/metrics")
@admin_required
def get_metrics():
    try:
        days = max(1, min(90, int(request.args.get("days", 7))))
    except ValueError:
        raise ValidationError("days must be a number") from None
    return jsonify(metrics.summary(days))
