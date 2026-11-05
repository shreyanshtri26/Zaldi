"""POST /api/chat: JSON ``{"message"}`` or multipart (``message`` + optional ``image``)."""
from flask import Blueprint, jsonify, request

from zaldi.api.shop import session_id
from zaldi.errors import ValidationError

bp = Blueprint("chat", __name__)


@bp.post("/chat")
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
    except Exception as exc:  # LLM or network failures should not surface as a 500 page
        return jsonify(error=f"chat failed: {exc}"), 502
