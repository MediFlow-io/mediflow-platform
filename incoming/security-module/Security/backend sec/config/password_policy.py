"""NIST SP 800-63B-aligned password validation policy.

This module rejects weak passwords using zxcvbn scoring and checks against the
HaveIBeenPwned (HIBP) breach API using k-anonymity. HIBP check uses
k-anonymity — only first 5 chars of SHA-1 hash are sent to the API.

The policy intentionally avoids arbitrary complexity rules because NIST guidance
recommends strong user-chosen passwords without mandatory pattern enforcement.

Example:
    >>> ok, msg = validate_password("CorrectHorseBatteryStaple!", {"email": "student@futa.edu.ng", "name": "Ada", "username": "ada01"})
    >>> ok
    True
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Final

import requests
from zxcvbn import zxcvbn


LOGGER: Final[logging.Logger] = logging.getLogger(__name__)
HIBP_API_URL: Final[str] = "https://api.pwnedpasswords.com/range/"


def _is_production() -> bool:
    """Return whether the application is running in a production-like environment."""
    return os.getenv("APP_ENV", "development").strip().lower() in {"production", "prod", "staging", "stage"}


def _normalize_context(user_context: dict[str, Any] | None) -> dict[str, str]:
    """Normalize a user context dictionary for name/email/username checks."""
    if not user_context:
        return {}

    context = {
        "email": str(user_context.get("email", "")).strip().lower(),
        "name": str(user_context.get("name", "")).strip().lower(),
        "username": str(user_context.get("username", "")).strip().lower(),
    }
    return {key: value for key, value in context.items() if value}


def _contains_user_reference(password: str, user_context: dict[str, Any] | None) -> bool:
    """Return whether the password contains the user's email, name, or username."""
    normalized = password.lower()
    context = _normalize_context(user_context)
    for value in context.values():
        if not value:
            continue
        if value in normalized:
            return True
        if len(value) > 3 and value.replace(" ", "") in normalized:
            return True
    return False


def _password_strength(password: str) -> int:
    """Score a password using zxcvbn and return the numeric strength score."""
    result = zxcvbn(password)
    return int(result.get("score", 0))


def _hibp_k_anonymity_check(password: str) -> bool:
    """Check HIBP using k-anonymity by sending only the first 5 hash chars.

    The HIBP API accepts a partial SHA-1 hash prefix and returns matching suffixes
    so the server never receives the full password hash.
    """
    sha1_hash = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix = sha1_hash[:5]
    suffix = sha1_hash[5:]

    try:
        response = requests.get(f"{HIBP_API_URL}{prefix}", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.warning("HIBP request failed during password breach check: %s", exc)
        return False

    for line in response.text.splitlines():
        candidate = line.split(":", 1)[0].strip()
        if candidate and candidate.upper() == suffix.upper():
            return True
    return False


def is_breached(password: str) -> bool:
    """Return whether the password appears in a known breach using HIBP.

    This function catches network failures gracefully. In development, password
    validation continues when the service is unavailable; in production, the check
    is treated as a hard rejection if the service fails.

    Args:
        password: The password to check.

    Returns:
        ``True`` if the password was found in the HIBP dataset, otherwise ``False``.
    """
    if not isinstance(password, str):
        return False
    if not password:
        return False

    try:
        return _hibp_k_anonymity_check(password)
    except Exception as exc:  # pragma: no cover - defensive guard
        LOGGER.warning("HIBP breach check error: %s", exc)
        if _is_production():
            return True
        return False


def validate_password(password: str, user_context: dict | None = None) -> tuple[bool, str]:
    """Validate a candidate password against the application password policy.

    Rules enforced:
        - minimum length: 12
        - maximum length: 128
        - zxcvbn score must be >= 3
        - password must not contain user email, name, or username
        - password must not be in the HIBP breach list

    Args:
        password: The candidate password.
        user_context: Optional user data such as email, name, and username.

    Returns:
        A ``(is_valid, error_message)`` tuple. When valid, ``error_message`` is an empty string.
    """
    if not isinstance(password, str):
        return False, "Password must be a string."

    if len(password) < 12:
        return False, "Password must be at least 12 characters long."

    if len(password) > 128:
        return False, "Password must be no more than 128 characters long."

    if _contains_user_reference(password, user_context):
        return False, "Password cannot contain your email, name, or username."

    if _password_strength(password) < 3:
        return False, "Password is too weak. Choose a stronger passphrase."

    if is_breached(password):
        return False, "This password has been found in a known data breach. Choose another password."

    return True, ""


__all__ = ["validate_password", "is_breached"]
