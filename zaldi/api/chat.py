"""POST /api/chat: JSON ``{"message"}`` or multipart (``message`` + optional ``image``).
POST /api/chat/stream: the same as server-sent events: one ``step`` event per tool call as it finishes, then ``done``."""
import json
import logging
import queue
import threading

from flask import Blueprint, Response, jsonify, request, stream_with_context

from zaldi import stores
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
    image, history, page = None, None, None
    if request.files.get("image"):
        upload = request.files["image"]
        image = (upload.read(), upload.mimetype)
        message = (request.form.get("message") or "").strip()
    else:
        body = request.get_json(silent=True) or {}
        message, history = (body.get("message") or "").strip(), body.get("history")
        page = body.get("page")
    if not message and not image:
        raise ValidationError("message is required")
    from zaldi.services.chat_service import handle_query  # lazy: pulls in the LLM stack

    try:
        return jsonify(handle_query(message, sid, image, history, page=page))
    except ValidationError:
        raise
    except Exception as exc:  # LLM or network failures: log the detail, show the customer a plain "try again" message
        log.exception("chat failed")
        busy = any(hint.lower() in str(exc).lower() for hint in QUOTA_HINTS)
        return jsonify(error=BUSY if busy else FAILED), 503 if busy else 502


@bp.post("/chat/stream")
@rate_limited("RATE_LIMIT_CHAT")
def post_chat_stream():
    sid = session_id()
    body = request.get_json(silent=True) or {}
    message, history = (body.get("message") or "").strip(), body.get("history")
    if not message:
        raise ValidationError("message is required")
    from zaldi.services.chat_service import handle_query

    events: queue.Queue = queue.Queue()

    def work():
        try:
            events.put(("done", handle_query(message, sid, None, history, on_step=lambda step: events.put(("step", step)))))
        except Exception as exc:
            log.exception("streamed chat failed")
            busy = any(hint.lower() in str(exc).lower() for hint in QUOTA_HINTS)
            events.put(("error", {"error": BUSY if busy else FAILED}))

    threading.Thread(target=stores.carry(work), daemon=True).start()

    def stream():
        while True:
            try:
                kind, data = events.get(timeout=60)
            except queue.Empty:
                kind, data = "error", {"error": FAILED}
            yield f"event: {kind}\ndata: {json.dumps(data, default=str)}\n\n"
            if kind in ("done", "error"):
                return

    return Response(stream_with_context(stream()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
