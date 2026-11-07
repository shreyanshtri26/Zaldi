"""Time-based one-time passwords (RFC 6238) for two-step sign-in with an authenticator app, using only the standard library.

A secret is 20 random bytes in base32 (what authenticator apps expect). A code is six digits that change every 30 seconds; the server
accepts the current step and one step either side (clock drift), and never accepts a step it has already accepted (replay).
"""
import base64
import hashlib
import hmac
import os
import struct
import time
import urllib.parse

STEP = 30
DIGITS = 6


def new_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode().rstrip("=")


def code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 10 ** DIGITS
    return f"{number:0{DIGITS}d}"


def _now() -> float:
    return time.time()  # a function of its own so a test can move the clock without touching every other timestamp


def verify(secret: str, code: str, after_step: int = 0, now: float | None = None, window: int = 1) -> int | None:
    """The step the code belongs to if it is valid and newer than ``after_step``; otherwise ``None``."""
    code = "".join((code or "").split())
    if not (len(code) == DIGITS and code.isdigit()):
        return None
    current = int((_now() if now is None else now) // STEP)
    for step in range(current - window, current + window + 1):
        if step > after_step and hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def uri(email: str, secret: str, issuer: str = "Zaldi") -> str:
    """The ``otpauth://`` address authenticator apps understand (most can also take the secret typed in by hand)."""
    label = urllib.parse.quote(f"{issuer}:{email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={urllib.parse.quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={STEP}"
