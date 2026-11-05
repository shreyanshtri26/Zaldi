"""POST /api/chat: JSON ``{"message"}`` or multipart (``message`` + optional ``image``)."""
import logging

from flask import Blueprint, jsonify, request

from zaldi.api.ratelimit import rate_limited
from zaldi.api.shop import session_id
from zaldi.errors import ValidationError

bp = Blueprint("chat", __name__)
log = logging.getLogger(__name__)
BUSY = "Zaldi is very busy right now. Please try again in a few minutes."
FAILED = "Zaldi couldn't answer just now. Please try again in a moment."
QUOTA_HINTS = ("RESOURCE_EXHAUSTED", "429", "quota", "rate limit", "rate_limit")


@bp.post("/chat")
@rate_limited("RATE_LIMIT_CHAT")
def post_chat():
    sid = session_id()
    image = None
    if request.files.get("image"):
        upload = request.files["image"]
        image = (upload.read(), upload.mimetype)
        message = (request.form.get("message") or "").strip()
    else:
        message = ((request.get_json(silent=True) or {}).get("message") or "").strip()
    if not message and not image:
        raise ValidationError("message is required")
    from zaldi.services.chat_service import handle_query  # lazy: pulls in the LLM stack

    try:
        return jsonify(handle_query(message, sid, image))
    except ValidationError:
        raise
    except Exception as exc:  # LLM or network failures: log the detail, show the customer a plain "try again" message
        log.exception("chat failed")
        busy = any(hint.lower() in str(exc).lower() for hint in QUOTA_HINTS)
        return jsonify(error=BUSY if busy else FAILED), 503 if busy else 502
