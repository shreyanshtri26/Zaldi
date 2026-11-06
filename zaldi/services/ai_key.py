"""Which AI model a store runs on: the provider (Gemini or Groq), its API key, and its model, all set from the admin dashboard.

Who pays for the model calls is the owner's choice: a store can run on the server's key or on its own. A store's keys are kept per store,
encrypted in that store's ``settings`` table (Fernet, derived from the server's ``SECRET_KEY``), and write-only: the dashboard is told
that a key is set (and its last four characters), never what it is. The model is chosen from the provider's own current list, so the
dropdown stays up to date without code changes.
"""
import base64
import hashlib
import logging
import re
import time

import requests
from cryptography.fernet import Fernet, InvalidToken

from zaldi import config, stores
from zaldi.db import override_repo
from zaldi.errors import ValidationError

log = logging.getLogger(__name__)
PROVIDER_SETTING = "ai.provider"
TTL = 30  # seconds a store's key and choices are remembered, so a chat does not read the database once per model call
MODELS_TTL = 600  # seconds the provider's model list is reused
_cache: dict[tuple, tuple[float, object]] = {}
_models_cache: dict[str, tuple[float, list[dict]]] = {}

PROVIDERS = {
    "google": {
        "label": "Gemini (Google)", "setting": "ai.google_api_key", "model_setting": "ai.google_model",
        "format": re.compile(r"AIza[0-9A-Za-z_\-]{30,60}"), "model_prefix": "gemini-",
        "bad_format": "That does not look like a Gemini API key. Keys start with AIza and are about 39 characters; copy it from Google AI Studio.",
        "fallback_models": ("gemini-3.5-flash", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"),
        "skip": ("embedding", "tts", "image", "live", "audio", "aqa", "imagen", "veo", "robotics", "computer-use", "learnlm", "native"),
        "quota_help": "The key is valid, but its free quota is used up. It resets daily, or you can enable billing in Google AI Studio.",
        "invalid_help": "Google did not accept this key. Check that you copied all of it and that the Generative Language API is enabled for it.",
    },
    "groq": {
        "label": "Groq", "setting": "ai.groq_api_key", "model_setting": "ai.groq_model",
        "format": re.compile(r"gsk_[0-9A-Za-z]{40,80}"), "model_prefix": "",
        "bad_format": "That does not look like a Groq API key. Keys start with gsk_; create one in the Groq console under API Keys.",
        "fallback_models": ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile"),
        "skip": ("whisper", "tts", "guard", "embed", "playai", "orpheus", "prompt-guard"),
        "quota_help": "The key is valid, but Groq's rate or daily limit is reached. Try again later or upgrade the plan in the Groq console.",
        "invalid_help": "Groq did not accept this key. Check that you copied all of it and that it has not been revoked.",
    },
}
MODEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/\-]{2,80}")


def _provider(name: str | None) -> str:
    name = name or "google"
    if name not in PROVIDERS:
        raise ValidationError("provider must be google or groq")
    return name


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("zaldi-ai-key:" + config.SECRET_KEY).encode()).digest()))


def _scope() -> tuple:
    return (stores.slug(), str(config.DB_PATH), config.PG_SCHEMA, bool(config.DATABASE_URL))


def _remember(kind: str, loader):
    scope, now = (kind,) + _scope(), time.monotonic()
    hit = _cache.get(scope)
    if hit and now - hit[0] < TTL:
        return hit[1]
    try:
        value = loader()
    except Exception:  # no database yet: behave as if nothing is set
        value = None
    _cache[scope] = (now, value)
    return value


def _forget(kind: str) -> None:
    _cache.pop((kind,) + _scope(), None)


def server_key(provider: str = "google") -> str | None:
    return (config.GOOGLE_API_KEY if _provider(provider) == "google" else config.GROQ_API_KEY) or None


def own_key(provider: str = "google") -> str | None:
    """The current store's own key for ``provider``, or ``None`` when it uses the server's."""
    provider = _provider(provider)

    def load():
        stored = override_repo.get_override("settings", PROVIDERS[provider]["setting"])
        if not stored:
            return None
        try:
            return _fernet().decrypt(stored.encode()).decode()
        except InvalidToken:
            log.warning("a saved %s key could not be decrypted (SECRET_KEY changed?); using the server's key", provider)
            return None

    return _remember("key:" + provider, load)


def key_for(provider: str = "google") -> str | None:
    """The key model calls use right now for ``provider``: the store's own, otherwise the server's."""
    return own_key(provider) or server_key(provider)


google_key = key_for  # the name the first version used


def set_key(raw: str, provider: str = "google") -> dict:
    provider = _provider(provider)
    raw = (raw or "").strip()
    if not PROVIDERS[provider]["format"].fullmatch(raw):
        raise ValidationError(PROVIDERS[provider]["bad_format"])
    override_repo.set_override("settings", PROVIDERS[provider]["setting"], _fernet().encrypt(raw.encode()).decode())
    _forget("key:" + provider)
    return status()


def clear_key(provider: str = "google") -> dict:
    provider = _provider(provider)
    override_repo.delete_override("settings", PROVIDERS[provider]["setting"])
    _forget("key:" + provider)
    return status()


# --- which provider -----------------------------------------------------------------------------------------------------------------
def chosen_provider() -> str | None:
    value = _remember("provider", lambda: override_repo.get_override("settings", PROVIDER_SETTING) or None)
    return value if value in PROVIDERS else None


def effective_provider() -> str:
    """The provider this store's chats use: its own pick, else the only one it has a key for, else the server's default."""
    pick = chosen_provider()
    if pick:
        return pick
    own = [p for p in PROVIDERS if own_key(p)]
    if len(own) == 1:
        return own[0]
    return config.LLM_PROVIDER if config.LLM_PROVIDER in PROVIDERS else "google"


def set_provider(name: str) -> dict:
    override_repo.set_override("settings", PROVIDER_SETTING, _provider(name))
    _forget("provider")
    return status()


def clear_provider() -> dict:
    override_repo.delete_override("settings", PROVIDER_SETTING)
    _forget("provider")
    return status()


# --- which model --------------------------------------------------------------------------------------------------------------------
def default_model(provider: str = "google") -> str:
    """The model used when the store has not picked one: the server's, if the server runs on this provider."""
    provider = _provider(provider)
    return config.LLM_MODEL if config.LLM_PROVIDER == provider else PROVIDERS[provider]["fallback_models"][0]


def chosen_model(provider: str = "google") -> str | None:
    """The model this store picked in the dashboard for ``provider``, or ``None`` for the default."""
    provider = _provider(provider)
    return _remember("model:" + provider, lambda: override_repo.get_override("settings", PROVIDERS[provider]["model_setting"]) or None)


def _order_google(name: str) -> tuple:
    version = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    tier = 0 if "pro" in name else 1 if "lite" not in name and "flash" in name else 2
    return (-(float(version.group(1)) if version else 0.0), tier, name)


def list_models(provider: str = "google") -> dict:
    """The chat models this store can choose from, asked from the provider with the key in use, newest first. Falls back to a built-in
    list when there is no key or the provider cannot be reached, and says so (``live`` is false)."""
    provider = _provider(provider)
    cfg = PROVIDERS[provider]
    key = key_for(provider)
    fallback = {"live": False, "models": [{"id": m, "label": m} for m in cfg["fallback_models"]]}
    if not key:
        return fallback
    tag = provider + hashlib.sha256(key.encode()).hexdigest()[:12]
    hit = _models_cache.get(tag)
    if hit and time.monotonic() - hit[0] < MODELS_TTL:
        return {"live": True, "models": hit[1]}
    found = []
    try:
        if provider == "google":  # the key goes in a header, never in the address
            response = requests.get("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": key}, params={"pageSize": 200}, timeout=10)
            response.raise_for_status()
            for m in response.json().get("models", []):
                name = str(m.get("name", "")).removeprefix("models/")
                if name.startswith("gemini-") and "generateContent" in (m.get("supportedGenerationMethods") or []) and not any(w in name for w in cfg["skip"]):
                    found.append({"id": name, "label": m.get("displayName") or name, "order": _order_google(name)})
            found.sort(key=lambda m: m["order"])
        else:
            response = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=10)
            response.raise_for_status()
            rows = [m for m in response.json().get("data", []) if m.get("active", True) and not any(w in str(m.get("id", "")).lower() for w in cfg["skip"])]
            for m in sorted(rows, key=lambda m: (-(m.get("created") or 0), str(m.get("id")))):
                found.append({"id": m["id"], "label": m["id"]})
    except Exception:
        return fallback
    for m in found:
        m.pop("order", None)
    if not found:
        return fallback
    _models_cache[tag] = (time.monotonic(), found)
    return {"live": True, "models": found}


def set_model(name: str, provider: str = "google") -> dict:
    provider = _provider(provider)
    name = (name or "").strip()
    if not MODEL_RE.fullmatch(name) or not name.startswith(PROVIDERS[provider]["model_prefix"]):
        raise ValidationError("Pick a model from the list.")
    listed = list_models(provider)
    if listed["live"] and name not in {m["id"] for m in listed["models"]}:
        raise ValidationError(f"{PROVIDERS[provider]['label']} does not list that model for your key. Pick one from the list.")
    override_repo.set_override("settings", PROVIDERS[provider]["model_setting"], name)
    _forget("model:" + provider)
    return status()


def clear_model(provider: str = "google") -> dict:
    provider = _provider(provider)
    override_repo.delete_override("settings", PROVIDERS[provider]["model_setting"])
    _forget("model:" + provider)
    return status()


# --- what the dashboard shows -------------------------------------------------------------------------------------------------------
def provider_status(provider: str) -> dict:
    own, picked = own_key(provider), chosen_model(provider)
    return {"label": PROVIDERS[provider]["label"], "source": "store" if own else "server" if server_key(provider) else "none",
            "own_key_set": bool(own), "own_key_hint": ("…" + own[-4:]) if own else None, "server_key_set": bool(server_key(provider)),
            "model": picked or default_model(provider), "model_is_default": picked is None, "default_model": default_model(provider)}


def status() -> dict:
    """Never a key itself. ``provider`` is the one this store's chats use now; ``provider_is_default`` is true until the owner picks one."""
    return {"provider": effective_provider(), "provider_is_default": chosen_provider() is None,
            "providers": {name: provider_status(name) for name in PROVIDERS}}


def test(provider: str | None = None) -> dict:
    """Make one tiny request with the key in use and say, in plain words, what happened. The key is never echoed back."""
    from zaldi.ai.models import get_llm

    provider = _provider(provider or effective_provider())
    cfg, key = PROVIDERS[provider], key_for(provider)
    if not key:
        return {"ok": False, "state": "none", "message": f"No {cfg['label']} key is set. Paste yours above, or ask the server admin to set one."}
    try:
        get_llm(provider).invoke("Reply with the single word: ok")
        return {"ok": True, "state": "working", "message": f"The key works with {chosen_model(provider) or default_model(provider)}."}
    except Exception as exc:
        low = str(exc).replace(key, "[key]").lower()
        if "429" in low or "resource_exhausted" in low or "quota" in low or "rate limit" in low or "rate_limit" in low:
            return {"ok": False, "state": "quota", "message": cfg["quota_help"]}
        if any(h in low for h in ("api key not valid", "api_key_invalid", "invalid api key", "invalid_api_key", "permission_denied", "401", "403", "400")):
            return {"ok": False, "state": "invalid", "message": cfg["invalid_help"]}
        return {"ok": False, "state": "error", "message": f"Could not reach {cfg['label']} just now. Try again in a moment."}
