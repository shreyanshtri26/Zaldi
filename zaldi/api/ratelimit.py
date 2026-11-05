"""Per-visitor request limit (in memory, per process): enough to stop LLM-cost abuse and token guessing."""
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request

from zaldi import config

_hits: dict[str, deque] = defaultdict(deque)


def client_ip() -> str:
    # Cloudflare puts the real visitor address in CF-Connecting-IP; otherwise use the socket address.
    return request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown"


def rate_limited(name: str):
    """``name`` is the config attribute holding the per-minute limit (0 disables the check)."""
    def decorate(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            limit = getattr(config, name)
            if limit:
                now, hits = time.monotonic(), _hits[f"{name}:{client_ip()}"]
                while hits and now - hits[0] > 60:
                    hits.popleft()
                if len(hits) >= limit:
                    return jsonify(error="too many requests, please wait a minute"), 429
                hits.append(now)
            return view(*args, **kwargs)
        return wrapper
    return decorate
