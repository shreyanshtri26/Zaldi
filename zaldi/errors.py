"""Domain errors, translated to HTTP responses in ``zaldi.api.errors``."""


class ValidationError(ValueError):
    """Client sent data that violates a rule (missing field, bad number, duplicate key)."""
