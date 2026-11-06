"""Keeps a rate-limited or briefly unavailable model from becoming a failed chat: retry with backoff, and a small TTL cache."""
import logging
import time
from functools import wraps

from zaldi import config

log = logging.getLogger(__name__)
TRANSIENT = ("429", "resource_exhausted", "rate limit", "rate_limit", "503", "unavailable", "overloaded", "timed out", "timeout", "connection")


def is_transient(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(hint in text for hint in TRANSIENT)


def retry(fn, attempts: int | None = None, base: float | None = None):
    """Call ``fn()``; on a transient error wait ``base * 2**n`` seconds and try again. Other errors are raised at once."""
    attempts = config.LLM_RETRIES if attempts is None else attempts
    base = config.LLM_RETRY_BASE if base is None else base
    for n in range(attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if n == attempts or not is_transient(exc):
                raise
            wait = base * (2 ** n)
            log.warning("transient model error (%s); retry %d/%d in %.1fs", type(exc).__name__, n + 1, attempts, wait)
            time.sleep(wait)


def ttl_cache(seconds: int, max_items: int = 256):
    """Cache a function's result per arguments for ``seconds``. For read-only lookups that cost an embedding call."""
    def deco(fn):
        store: dict = {}

        @wraps(fn)
        def inner(*args):
            now = time.monotonic()
            hit = store.get(args)
            if hit and now - hit[0] < seconds:
                return hit[1]
            value = fn(*args)
            if len(store) >= max_items:
                store.pop(next(iter(store)))
            store[args] = (now, value)
            return value
        inner.cache_clear = store.clear
        return inner
    return deco
