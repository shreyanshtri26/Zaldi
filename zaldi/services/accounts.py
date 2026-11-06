"""Store owner accounts. The person who builds a shop signs in with their own email and password and can manage only their store.

Accounts live in the default database (``admin_users``). A successful login returns a signed token that carries the account's
store and role; it is sent in the same ``X-Admin-Token`` header as the server admin's token. Roles: ``owner`` can change
everything in the store, ``viewer`` can only read (chats, metrics, products).
"""
import re

from werkzeug.security import check_password_hash, generate_password_hash

from zaldi import config, stores
from zaldi.checkout.tokens import sign, unsign
from zaldi.db.connection import connect
from zaldi.errors import ValidationError

SALT = "store-owner"
TOKEN_TTL = 12 * 3600
ROLES = ("owner", "viewer")
EMAIL = re.compile(r"[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}")
MIN_PASSWORD = 10


def create_account(email: str, password: str, store: str, role: str = "owner") -> dict:
    email = (email or "").strip().lower()
    if not EMAIL.fullmatch(email) or len(email) > 120:
        raise ValidationError("enter a valid email address")
    if len(password or "") < MIN_PASSWORD:
        raise ValidationError(f"the password needs at least {MIN_PASSWORD} characters")
    if role not in ROLES:
        raise ValidationError("role must be owner or viewer")
    if not stores.exists(store):
        raise ValidationError("unknown store")
    with connect(store=stores.DEFAULT) as conn:
        if conn.execute("SELECT 1 FROM admin_users WHERE email = ?", (email,)).fetchone():
            raise ValidationError("an account with that email already exists")
        conn.execute("INSERT INTO admin_users (email, password_hash, store, role) VALUES (?, ?, ?, ?)",
                     (email, generate_password_hash(password), store, role))
    return {"email": email, "store": store, "role": role}


def authenticate(email: str, password: str) -> dict:
    """The account for these credentials, or the same vague error for a wrong email and a wrong password."""
    with connect(store=stores.DEFAULT) as conn:
        row = conn.execute("SELECT * FROM admin_users WHERE email = ?", ((email or "").strip().lower(),)).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password or ""):
        raise ValidationError("wrong email or password")
    return {"email": row["email"], "store": row["store"], "role": row["role"]}


def issue_token(account: dict) -> str:
    return sign(SALT, {"email": account["email"], "store": account["store"], "role": account["role"]})


def verify_token(token: str) -> dict | None:
    """The account a token was issued to, if the token is genuine and unexpired and the account still exists."""
    try:
        data = unsign(SALT, token, TOKEN_TTL)
    except ValidationError:
        return None
    with connect(store=stores.DEFAULT) as conn:
        row = conn.execute("SELECT email, store, role FROM admin_users WHERE email = ?", (data.get("email"),)).fetchone()
    return dict(row) if row and row["store"] == data.get("store") and row["role"] == data.get("role") else None


def list_accounts(store: str) -> list[dict]:
    with connect(store=stores.DEFAULT) as conn:
        return [dict(r) for r in conn.execute("SELECT email, role, created_at FROM admin_users WHERE store = ? ORDER BY email", (store,))]


def signup(email: str, password: str, store: str, name: str) -> dict:
    """Self-service: make a new store and its first owner. Off unless ``ALLOW_SIGNUP=1``."""
    if not config.ALLOW_SIGNUP:
        raise ValidationError("sign-up is not open on this server")
    if len(password or "") < MIN_PASSWORD or not EMAIL.fullmatch((email or "").strip().lower()):
        raise ValidationError("enter a valid email and a password of at least 10 characters")
    created = stores.create_store(store, name)
    try:
        account = create_account(email, password, created["slug"])
    except ValidationError:
        stores.delete_store(created["slug"])  # do not leave an owner-less store behind
        raise
    return {"account": account, "token": issue_token(account), "store": created}


def change_password(email: str, current: str, new: str) -> dict:
    """An account changes its own password: the current one must be right, the new one must be different and long enough."""
    account = authenticate(email, current)
    if new == current:
        raise ValidationError("The new password must be different from the current one.")
    if len(new or "") < MIN_PASSWORD:
        raise ValidationError(f"Use at least {MIN_PASSWORD} characters for the new password.")
    with connect(store=stores.DEFAULT) as conn:
        conn.execute("UPDATE admin_users SET password_hash = ? WHERE email = ?", (generate_password_hash(new), account["email"]))
    return {"ok": True}
