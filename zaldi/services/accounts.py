"""Store owner accounts. The person who builds a shop signs in with their own email and password and can manage only their store.

Accounts live in the default database (``admin_users``). A successful sign-in returns a signed token carrying the account's store, role
and *auth version*; it is sent in the same ``X-Admin-Token`` header as the server admin's token. Roles: ``owner`` can change everything
in the store, ``viewer`` can only read.

Security features
* **Two-step sign-in** (optional, per account): a code from an authenticator app (TOTP) after the password, plus one-time recovery codes.
  A code can be used only once.
* **Password reset:** a signed, one-hour, single-use link. The server admin can create one for any account; if the server can send email,
  an owner can ask for one themselves. Resetting does not turn two-step off.
* **Sessions end when credentials change:** a password change or reset, a role change, or turning two-step off raises the account's auth
  version, so every token issued earlier stops working.
* **Guessing is slowed down:** five wrong attempts in ten minutes lock that account for the rest of the window.
"""
import base64
import hashlib
import json
import re
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken
from werkzeug.security import check_password_hash, generate_password_hash

from zaldi import config, stores
from zaldi.checkout.tokens import sign, unsign
from zaldi.db.connection import connect
from zaldi.errors import ValidationError
from zaldi.services import mailer, totp

SALT = "store-owner"
LOGIN_SALT = "store-owner-2fa"
RESET_SALT = "store-owner-reset"
TOKEN_TTL = 12 * 3600
CHALLENGE_TTL = 300
RESET_TTL = 3600
ROLES = ("owner", "viewer")
EMAIL = re.compile(r"[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}")
MIN_PASSWORD = 10
RECOVERY_CODES = 8
LOCK_AFTER, LOCK_WINDOW = 5, 600
COOLDOWN = 60  # seconds between "forgot password" emails to the same account
_failures: dict[str, list[float]] = {}
_last_reset_mail: dict[str, float] = {}


def _clean_email(email: str) -> str:
    return (email or "").strip().lower()


def _row(email: str):
    with connect(store=stores.DEFAULT) as conn:
        return conn.execute("SELECT * FROM admin_users WHERE email = ?", (_clean_email(email),)).fetchone()


def _public(row) -> dict:
    return {"email": row["email"], "store": row["store"], "role": row["role"]}


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("zaldi-totp:" + config.SECRET_KEY).encode()).digest()))


def _hash_code(code: str) -> str:
    return hashlib.sha256((config.SECRET_KEY + ":recovery:" + code.strip().lower()).encode()).hexdigest()


def _check_lock(email: str) -> None:
    now = time.monotonic()
    recent = [t for t in _failures.get(email, []) if now - t < LOCK_WINDOW]
    _failures[email] = recent
    if len(recent) >= LOCK_AFTER:
        raise ValidationError("Too many wrong attempts. Wait a few minutes and try again.")


def _fail(email: str, message: str):
    _failures.setdefault(email, []).append(time.monotonic())
    raise ValidationError(message)


def _bump(email: str, **changes) -> None:
    """Update columns and raise the auth version, which ends every session issued before now."""
    sets = "".join(f"{k} = ?, " for k in changes)
    with connect(store=stores.DEFAULT) as conn:
        conn.execute(f"UPDATE admin_users SET {sets}auth_version = auth_version + 1 WHERE email = ?", [*changes.values(), _clean_email(email)])


def _fresh_token(email: str) -> str:
    row = _row(email)
    return issue_token({**_public(row), "av": row["auth_version"] or 0})


# --- creating and signing in -------------------------------------------------------------------------------------------------------------
def create_account(email: str, password: str, store: str, role: str = "owner") -> dict:
    email = _clean_email(email)
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
    """The account for these credentials, or the same vague error for a wrong email and a wrong password. Counts wrong attempts."""
    email = _clean_email(email)
    _check_lock(email)
    row = _row(email)
    if row is None or not check_password_hash(row["password_hash"], password or ""):
        _fail(email, "wrong email or password")
    return {**_public(row), "av": row["auth_version"] or 0, "two_step": bool(row["totp_enabled"])}


def issue_token(account: dict) -> str:
    return sign(SALT, {"email": account["email"], "store": account["store"], "role": account["role"], "av": account.get("av", 0)})


def verify_token(token: str) -> dict | None:
    """The account a token was issued to, if the token is genuine and unexpired, the account still exists, and nothing that ends
    sessions (a password change, a reset, a role change) has happened since."""
    try:
        data = unsign(SALT, token, TOKEN_TTL)
    except ValidationError:
        return None
    row = _row(data.get("email", ""))
    if row is None or row["store"] != data.get("store") or row["role"] != data.get("role") or (row["auth_version"] or 0) != data.get("av", 0):
        return None
    return _public(row)


def _signed_in(account: dict) -> dict:
    return {"token": issue_token(account), "email": account["email"], "store": account["store"], "role": account["role"]}


def begin_login(email: str, password: str) -> dict:
    """Step one. Returns the token, or ``{"needs_two_step": True, "challenge"}`` when the account has two-step sign-in on."""
    account = authenticate(email, password)
    if account["two_step"]:
        return {"needs_two_step": True, "challenge": sign(LOGIN_SALT, {"email": account["email"], "av": account["av"]})}
    _failures.pop(account["email"], None)
    return _signed_in(account)


def finish_login(challenge: str, code: str) -> dict:
    """Step two: the code from the authenticator app (or a recovery code)."""
    try:
        data = unsign(LOGIN_SALT, challenge, CHALLENGE_TTL)
    except ValidationError:
        raise ValidationError("That sign-in took too long. Start again.") from None
    email = _clean_email(data.get("email", ""))
    _check_lock(email)
    row = _row(email)
    if row is None or (row["auth_version"] or 0) != data.get("av", 0) or not row["totp_enabled"]:
        raise ValidationError("That sign-in is no longer valid. Start again.")
    if not _second_factor_ok(row, code):
        _fail(email, "That code is not right. Codes change every 30 seconds.")
    _failures.pop(email, None)
    return _signed_in({**_public(row), "av": row["auth_version"] or 0})


def list_accounts(store: str) -> list[dict]:
    with connect(store=stores.DEFAULT) as conn:
        rows = conn.execute("SELECT email, role, created_at, totp_enabled FROM admin_users WHERE store = ? ORDER BY email", (store,)).fetchall()
    return [{"email": r["email"], "role": r["role"], "created_at": r["created_at"], "two_step": bool(r["totp_enabled"])} for r in rows]


def signup(email: str, password: str, store: str, name: str) -> dict:
    """Self-service: make a new store and its first owner. Off unless ``ALLOW_SIGNUP=1``."""
    if not config.ALLOW_SIGNUP:
        raise ValidationError("sign-up is not open on this server")
    if len(password or "") < MIN_PASSWORD or not EMAIL.fullmatch(_clean_email(email)):
        raise ValidationError("enter a valid email and a password of at least 10 characters")
    created = stores.create_store(store, name)
    try:
        account = create_account(email, password, created["slug"])
    except ValidationError:
        stores.delete_store(created["slug"])  # do not leave an owner-less store behind
        raise
    return {"account": account, "token": issue_token(authenticate(email, password)), "store": created}


# --- password ----------------------------------------------------------------------------------------------------------------------------
def change_password(email: str, current: str, new: str) -> dict:
    """An account changes its own password. Every other session of the account ends; the caller gets a fresh token."""
    account = authenticate(email, current)
    if new == current:
        raise ValidationError("The new password must be different from the current one.")
    if len(new or "") < MIN_PASSWORD:
        raise ValidationError(f"Use at least {MIN_PASSWORD} characters for the new password.")
    _bump(account["email"], password_hash=generate_password_hash(new))
    return {"ok": True, "token": _fresh_token(account["email"])}


def create_reset(email: str) -> str:
    """A one-hour, single-use reset token for an account. Making a new one cancels any earlier one."""
    row = _row(email)
    if row is None:
        raise ValidationError("That account does not exist.")
    nonce = secrets.token_urlsafe(16)
    with connect(store=stores.DEFAULT) as conn:
        conn.execute("UPDATE admin_users SET reset_nonce = ? WHERE email = ?", (nonce, row["email"]))
    return sign(RESET_SALT, {"email": row["email"], "nonce": nonce})


def reset_password(token: str, new: str) -> dict:
    try:
        data = unsign(RESET_SALT, token, RESET_TTL)
    except ValidationError:
        raise ValidationError("This reset link is invalid or has expired. Ask for a new one.") from None
    row = _row(data.get("email", ""))
    if row is None or not row["reset_nonce"] or not secrets.compare_digest(row["reset_nonce"], data.get("nonce", "")):
        raise ValidationError("This reset link has already been used or was replaced. Ask for a new one.")
    if len(new or "") < MIN_PASSWORD:
        raise ValidationError(f"Use at least {MIN_PASSWORD} characters for the new password.")
    _bump(row["email"], password_hash=generate_password_hash(new), reset_nonce=None)
    _failures.pop(row["email"], None)  # a reset also clears a lock from guessing
    return {"ok": True, "email": row["email"]}


def forgot_password(email: str, base_url: str) -> dict:
    """Self-service reset by email. The answer never says whether the account exists. Nothing is sent unless the server can send email."""
    email = _clean_email(email)
    row = _row(email) if EMAIL.fullmatch(email) else None
    now = time.monotonic()
    if row is not None and mailer.enabled() and now - _last_reset_mail.get(email, -COOLDOWN) >= COOLDOWN:
        _last_reset_mail[email] = now
        link = f"{base_url.rstrip('/')}/admin?reset={create_reset(email)}"
        mailer.send(email, "Reset your Zaldi password",
                    f"Someone asked to reset the password for your Zaldi account.\n\nOpen this link within one hour to choose a new one:\n{link}\n\n"
                    "If it was not you, ignore this email: your password has not changed.")
    return {"ok": True, "email_enabled": mailer.enabled()}


# --- two-step sign-in -------------------------------------------------------------------------------------------------------------------
def _second_factor_ok(row, code: str) -> bool:
    """A valid authenticator code (each step usable once) or an unused recovery code (consumed when used)."""
    code = (code or "").strip()
    if row["totp_secret"]:
        try:
            secret = _fernet().decrypt(row["totp_secret"].encode()).decode()
        except InvalidToken:
            secret = None
        step = totp.verify(secret, code, row["totp_last_step"] or 0) if secret else None
        if step is not None:
            with connect(store=stores.DEFAULT) as conn:
                conn.execute("UPDATE admin_users SET totp_last_step = ? WHERE email = ?", (step, row["email"]))
            return True
    codes = json.loads(row["recovery_codes"] or "[]")
    digest = _hash_code(code)
    if len(code) >= 8 and digest in codes:
        codes.remove(digest)
        with connect(store=stores.DEFAULT) as conn:
            conn.execute("UPDATE admin_users SET recovery_codes = ? WHERE email = ?", (json.dumps(codes), row["email"]))
        return True
    return False


def two_step_status(email: str) -> dict:
    row = _row(email)
    return {"enabled": bool(row["totp_enabled"]), "recovery_codes_left": len(json.loads(row["recovery_codes"] or "[]")) if row["totp_enabled"] else 0}


def begin_two_step(email: str, password: str) -> dict:
    """Start turning two-step on: make a secret (not active until a code proves the app has it). Needs the password again."""
    account = authenticate(email, password)
    if account["two_step"]:
        raise ValidationError("Two-step sign-in is already on.")
    secret = totp.new_secret()
    with connect(store=stores.DEFAULT) as conn:
        conn.execute("UPDATE admin_users SET totp_secret = ?, totp_enabled = 0, totp_last_step = 0 WHERE email = ?",
                     (_fernet().encrypt(secret.encode()).decode(), account["email"]))
    return {"secret": secret, "uri": totp.uri(account["email"], secret)}


def confirm_two_step(email: str, code: str) -> dict:
    """Finish turning two-step on with a first code. Returns the recovery codes, shown once."""
    row = _row(email)
    if row is None or row["totp_enabled"] or not row["totp_secret"]:
        raise ValidationError("Start by asking for a new secret.")
    _check_lock(row["email"])
    secret = _fernet().decrypt(row["totp_secret"].encode()).decode()
    step = totp.verify(secret, code)
    if step is None:
        _fail(row["email"], "That code is not right. Check the app and try the current code.")
    plain = [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(RECOVERY_CODES)]
    with connect(store=stores.DEFAULT) as conn:
        conn.execute("UPDATE admin_users SET totp_enabled = 1, totp_last_step = ?, recovery_codes = ? WHERE email = ?",
                     (step, json.dumps([_hash_code(c) for c in plain]), row["email"]))
    return {"recovery_codes": plain}


def disable_two_step(email: str, password: str, code: str) -> dict:
    """The account turns two-step off: needs the password and a current code (or a recovery code). Ends other sessions."""
    account = authenticate(email, password)
    row = _row(account["email"])
    if not row["totp_enabled"]:
        raise ValidationError("Two-step sign-in is not on.")
    if not _second_factor_ok(row, code):
        _fail(account["email"], "That code is not right.")
    _bump(account["email"], totp_secret=None, totp_enabled=0, totp_last_step=0, recovery_codes=None)
    return {"ok": True, "token": _fresh_token(account["email"])}


# --- managed by the server admin ----------------------------------------------------------------------------------------------------------
def _account_in(store: str, email: str):
    row = _row(email)
    if row is None or row["store"] != store:
        raise ValidationError("That account is not in this store.")
    return row


def delete_account(store: str, email: str) -> None:
    _account_in(store, email)
    with connect(store=stores.DEFAULT) as conn:
        conn.execute("DELETE FROM admin_users WHERE email = ?", (_clean_email(email),))


def set_role(store: str, email: str, role: str) -> dict:
    if role not in ROLES:
        raise ValidationError("role must be owner or viewer")
    row = _account_in(store, email)
    _bump(row["email"], role=role)  # the old token carries the old role: it must stop working
    return {"email": row["email"], "role": role}


def admin_turn_off_two_step(store: str, email: str) -> dict:
    """For a lost phone: the server admin turns two-step off for an account. The owner can turn it on again."""
    row = _account_in(store, email)
    _bump(row["email"], totp_secret=None, totp_enabled=0, totp_last_step=0, recovery_codes=None)
    return {"email": row["email"], "two_step": False}
