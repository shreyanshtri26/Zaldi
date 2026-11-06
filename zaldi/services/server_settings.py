"""Settings for the whole server (not one shop), changeable by the server admin from the portal: the admin password and the database.

* **Admin password.** The server admin's credential is the ``ADMIN_TOKEN`` environment variable. From the portal the admin can set a
  password of their own; it is stored as a salted hash in the default store's settings. The environment token keeps working as a recovery
  key, so a forgotten password can never lock the admin out; remove it from the host's settings to rely on the portal password alone.
* **Database.** The Postgres address is needed before the app can read any database, so a choice made in the portal is saved in an encrypted
  file on the server's disk (see ``bootstrap``) and takes effect on the next restart. The portal can test an address, copy the existing data
  into it, save it, and restart the server.
"""
import hashlib
import os
import subprocess
import sys
import time
import urllib.parse

from werkzeug.security import check_password_hash, generate_password_hash

from zaldi import bootstrap, config, stores
from zaldi.connectors import netguard
from zaldi.db import override_repo
from zaldi.errors import ValidationError

PASSWORD_SETTING = "server.admin_password_hash"
MIN_PASSWORD = 12
VERIFY_TTL = 300  # seconds a correct password is remembered, so scrypt does not run on every admin request
_verified: dict[str, float] = {}


# --- admin password -------------------------------------------------------------------------------------------------------------------
def _stored_hash() -> str | None:
    try:
        with stores.use(stores.DEFAULT):
            return override_repo.get_override("settings", PASSWORD_SETTING) or None
    except Exception:
        return None


def has_portal_password() -> bool:
    return bool(_stored_hash())


def portal_password_matches(given: str) -> bool:
    stored = _stored_hash()
    if not stored or not given:
        return False
    tag = hashlib.sha256((stored + "\n" + given).encode()).hexdigest()
    if _verified.get(tag, 0) > time.monotonic():
        return True
    if check_password_hash(stored, given):
        _verified[tag] = time.monotonic() + VERIFY_TTL
        return True
    return False


def _is_current(given: str) -> bool:
    import hmac

    return bool(given) and ((bool(config.ADMIN_TOKEN) and hmac.compare_digest(given, config.ADMIN_TOKEN)) or portal_password_matches(given))


def set_password(current: str, new: str) -> dict:
    if not _is_current(current):
        raise ValidationError("The current password is wrong.")
    if new == current:
        raise ValidationError("The new password must be different from the current one.")
    if len(new or "") < MIN_PASSWORD:
        raise ValidationError(f"Use at least {MIN_PASSWORD} characters for the new password.")
    with stores.use(stores.DEFAULT):
        override_repo.set_override("settings", PASSWORD_SETTING, generate_password_hash(new))
    _verified.clear()
    return status()


def clear_password(current: str) -> dict:
    """Go back to the environment ``ADMIN_TOKEN`` alone."""
    if not _is_current(current):
        raise ValidationError("The current password is wrong.")
    if not config.ADMIN_TOKEN:
        raise ValidationError("There is no ADMIN_TOKEN in the server's environment, so removing the portal password would lock everyone out.")
    with stores.use(stores.DEFAULT):
        override_repo.delete_override("settings", PASSWORD_SETTING)
    _verified.clear()
    return status()


# --- database -------------------------------------------------------------------------------------------------------------------------
def _describe(url: str) -> dict:
    """Host and database name only: never the user, the password or the query string."""
    parts = urllib.parse.urlparse(url)
    return {"host": parts.hostname or "", "database": parts.path.lstrip("/") or ""}


def _saved_url() -> str:
    return bootstrap.load(config.DATA_DIR, config.SECRET_KEY)


def status() -> dict:
    running = config.DATABASE_URL
    saved = _saved_url()
    env = bool(os.getenv("DATABASE_URL"))
    return {
        "admin_password": {"source": "portal" if has_portal_password() else "environment", "environment_token_set": bool(config.ADMIN_TOKEN),
                           "min_length": MIN_PASSWORD},
        "database": {"backend": "postgres" if running else "sqlite", **(_describe(running) if running else {"host": "", "database": ""}),
                     "schema": config.PG_SCHEMA if running else None,
                     "source": "environment" if env else "portal" if running else "default",
                     "saved_in_portal": bool(saved), "saved": _describe(saved) if saved else None,
                     "restart_needed": bool(saved) and saved != running and not env, "environment_overrides": env and bool(saved) and saved != running},
    }


def _clean_url(url: str) -> str:
    url = (url or "").strip()
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ("postgresql", "postgres") or not parts.hostname:
        raise ValidationError("Use a Postgres address that starts with postgresql:// (for Neon, copy the pooled connection string).")
    if len(url) > 600:
        raise ValidationError("That address is too long.")
    return url


def test_database(url: str) -> dict:
    """Try an address and report in plain words. The address (with its password) is never put in a message."""
    url = _clean_url(url)
    try:
        netguard.check_public_url("https://" + urllib.parse.urlparse(url).hostname)
    except ValidationError as exc:
        return {"ok": False, "state": "blocked", "message": str(exc)}
    try:
        import psycopg

        with psycopg.connect(url, connect_timeout=10, autocommit=True) as conn:
            version = conn.execute("SHOW server_version").fetchone()[0]
            vector = conn.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'").fetchone() is not None
            has_data = False
            table = conn.execute("SELECT to_regclass(%s)", (f'"{config.PG_SCHEMA}".products',)).fetchone()[0]
            if table:
                has_data = conn.execute(f'SELECT 1 FROM "{config.PG_SCHEMA}".products LIMIT 1').fetchone() is not None
    except Exception as exc:
        low = str(exc).lower()
        if "password authentication failed" in low or "authentication failed" in low:
            return {"ok": False, "state": "auth", "message": "The database refused the username or password."}
        if "could not translate host" in low or "name or service not known" in low or "getaddrinfo" in low:
            return {"ok": False, "state": "unreachable", "message": "That database host could not be found. Check the address."}
        if "timeout" in low or "timed out" in low:
            return {"ok": False, "state": "unreachable", "message": "The database did not answer in time. Check the address and that it allows connections."}
        return {"ok": False, "state": "error", "message": "Could not connect. Check the whole address, including ?sslmode=require for Neon."}
    if not vector:
        return {"ok": False, "state": "no_vector", "message": "Connected, but this database does not offer the pgvector extension, which Zaldi needs for search. Neon includes it."}
    return {"ok": True, "state": "ok", "message": "Connected.", "version": version, "has_data": has_data, **_describe(url)}


def save_database(url: str) -> dict:
    url = _clean_url(url)
    result = test_database(url)
    if not result["ok"]:
        raise ValidationError(result["message"])
    bootstrap.save(config.DATA_DIR, config.SECRET_KEY, url)
    return status()


def clear_database() -> dict:
    bootstrap.clear(config.DATA_DIR)
    return status()


def copy_database(url: str, replace: bool = False) -> dict:
    """Copy this server's SQLite data into the Postgres at ``url``. It runs in a separate process, so the running app keeps using
    its own database untouched while it works."""
    url = _clean_url(url)
    result = test_database(url)
    if not result["ok"]:
        raise ValidationError(result["message"])
    if result["has_data"] and not replace:
        raise ValidationError("That database already has Zaldi data. Choose to replace it, or use an empty database.")
    command = [sys.executable, "-m", "zaldi", "migrate"] + (["--replace"] if replace else [])
    try:
        done = subprocess.run(command, env={**os.environ, "DATABASE_URL": url}, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        raise ValidationError("Copying took too long and was stopped. Nothing was changed on this server.") from None
    lines = [line for line in (done.stdout + "\n" + done.stderr).replace(url, "[address]").splitlines() if line.strip()]
    if done.returncode != 0:
        last = lines[-1] if lines else ""
        raise ValidationError(last if last and "[address]" not in last and "Traceback" not in last else "The copy failed. Nothing on this server was changed.")
    return {"ok": True, "report": [line for line in lines if not line.startswith(" ")][-12:]}
