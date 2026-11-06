"""Settings the app needs *before* it can open its database, so they cannot live in the database.

Today that is one thing: the Postgres address chosen in the admin portal. It is kept encrypted (Fernet, derived from ``SECRET_KEY``) in
``<data dir>/bootstrap.json`` on the server's own disk. An environment ``DATABASE_URL`` always wins over it. Nothing here imports the
rest of the app, because ``config`` reads it while the app is still starting.
"""
import base64
import hashlib
import json
from pathlib import Path

from cryptography.fernet import Fernet

FILE = "bootstrap.json"


def _fernet(secret: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("zaldi-bootstrap:" + secret).encode()).digest()))


def load(data_dir: Path, secret: str) -> str:
    """The saved Postgres address, or an empty string when none was saved or it cannot be read."""
    try:
        token = json.loads((Path(data_dir) / FILE).read_text(encoding="utf-8"))["database_url"]
        return _fernet(secret).decrypt(token.encode()).decode()
    except Exception:
        return ""


def save(data_dir: Path, secret: str, url: str) -> None:
    path = Path(data_dir) / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"database_url": _fernet(secret).encrypt(url.encode()).decode()}), encoding="utf-8")


def clear(data_dir: Path) -> None:
    (Path(data_dir) / FILE).unlink(missing_ok=True)


def exists(data_dir: Path) -> bool:
    return (Path(data_dir) / FILE).exists()
