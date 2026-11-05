"""Signed, expiring tokens (itsdangerous ships with Flask). A token proves the server issued it; it never grants more than its payload."""
from itsdangerous import BadSignature, URLSafeTimedSerializer

from zaldi import config
from zaldi.errors import ValidationError


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.SECRET_KEY, salt=salt)


def sign(salt: str, payload: dict) -> str:
    return _serializer(salt).dumps(payload)


def unsign(salt: str, token: str, max_age: int) -> dict:
    try:
        return _serializer(salt).loads(token, max_age=max_age)
    except BadSignature:  # also covers expiry (SignatureExpired is a subclass)
        raise ValidationError("this link is invalid or has expired") from None
