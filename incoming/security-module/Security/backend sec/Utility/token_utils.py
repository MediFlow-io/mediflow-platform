"""Secure token generation utilities for sessions, reset links, MFA backup codes, and API keys.

This module intentionally uses Python's ``secrets`` module for all token generation.
It avoids predictable values and provides a constant-time comparison helper for
sensitive token verification.

Example:
    >>> session_id = generate_session_id()
    >>> reset_token = generate_password_reset_token()
    >>> raw_key, hashed_key = generate_api_key()
    >>> backup_codes = generate_backup_codes(3)
    >>> len(session_id) > 0
    True
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import string
from typing import Final

# Never use `random` module for security tokens

_ALLOWED_BACKUP_CHARACTERS: Final[str] = string.ascii_letters + string.digits


def _generate_urlsafe_token(byte_length: int = 32) -> str:
    """Generate a URL-safe, cryptographically secure random token.

    Args:
        byte_length: Number of random bytes to generate before encoding.

    Returns:
        A URL-safe base64-encoded token without padding characters.
    """
    token_bytes = secrets.token_bytes(byte_length)
    return base64.urlsafe_b64encode(token_bytes).rstrip(b"=").decode("ascii")


def generate_session_id() -> str:
    """Generate a secure session identifier.

    Returns:
        A 32-byte random session ID encoded as URL-safe base64.
    """
    return _generate_urlsafe_token(32)


def generate_password_reset_token() -> str:
    """Generate a cryptographically secure password reset token.

    Returns:
        A 32-byte random password reset token encoded as URL-safe base64.
    """
    return _generate_urlsafe_token(32)


def generate_email_verification_token() -> str:
    """Generate a cryptographically secure email verification token.

    Returns:
        A 32-byte random email verification token encoded as URL-safe base64.
    """
    return _generate_urlsafe_token(32)


def generate_api_key() -> tuple[str, str]:
    """Generate a raw API key and a one-way hash for secure storage.

    Returns:
        A tuple of ``(raw_key, hashed_key)`` where the raw key is suitable for
        distribution to clients and the hash is suitable for verification or
        persistence in a database.
    """
    raw_key = _generate_urlsafe_token(32)
    hashed_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return raw_key, hashed_key


def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate human-readable MFA backup codes.

    Args:
        count: Number of unique backup codes to generate.

    Returns:
        A list of unique backup codes, each exactly 8 characters long and
        containing only alphanumeric characters.

    Raises:
        TypeError: If the count is not an integer.
        ValueError: If the count is less than 1.
    """
    if not isinstance(count, int):
        raise TypeError("count must be an integer")
    if count < 1:
        raise ValueError("count must be at least 1")

    codes: set[str] = set()
    result: list[str] = []

    while len(result) < count:
        candidate = "".join(secrets.choice(_ALLOWED_BACKUP_CHARACTERS) for _ in range(8))
        if candidate not in codes:
            codes.add(candidate)
            result.append(candidate)

    return result


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings using a constant-time algorithm.

    This helper is intended for comparing secret values such as API keys,
    password-reset tokens, or MFA codes where timing side-channels must be
    avoided.

    Args:
        a: First string to compare.
        b: Second string to compare.

    Returns:
        ``True`` when the strings are equal, otherwise ``False``.

    Raises:
        TypeError: If either value is not a string.
    """
    if not isinstance(a, str) or not isinstance(b, str):
        raise TypeError("a and b must both be strings")
    return secrets.compare_digest(a, b)


__all__ = [
    "generate_session_id",
    "generate_password_reset_token",
    "generate_email_verification_token",
    "generate_api_key",
    "generate_backup_codes",
    "constant_time_compare",
]
