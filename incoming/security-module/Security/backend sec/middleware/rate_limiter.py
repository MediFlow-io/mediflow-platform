"""Flask-Limiter configuration with Redis-backed rate limiting.

This module provides a shared limiter instance and default per-IP/per-user
limits, ensuring that brute-force attempts and abusive API traffic are controlled
before reaching application logic.

Example:
    >>> from flask import Flask
    >>> app = Flask(__name__)
    >>> app.config['RATELIMIT_STORAGE_URI'] = 'redis://localhost:6379/0'
    >>> init_limiter(app)
    >>> @app.route('/login')
    ... @limiter.limit(LOGIN_LIMIT)
    ... def login():
    ...     return {'status': 'ok'}
"""

from __future__ import annotations

import os
from typing import Any, Final

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


LOGIN_LIMIT: Final[str] = "5 per 15 minutes"
REGISTER_LIMIT: Final[str] = "3 per hour"
PASSWORD_RESET_LIMIT: Final[str] = "3 per hour"
MFA_VERIFY_LIMIT: Final[str] = "10 per 15 minutes"
API_DEFAULT_LIMIT: Final[str] = "200 per minute"


def _get_limiter_key() -> str:
    """Return a key that uniquely identifies the caller using user_id and IP."""
    user = getattr(request, "user", None)
    user_id = getattr(user, "id", None) if user is not None else None
    ip = get_remote_address(request) or "unknown"
    return f"{user_id or 'anonymous'}:{ip}"


def _rate_limit_exceeded(_: Any, response: Any, key: str | None) -> Any:
    """Return a JSON 429 response describing the rate limit breach."""
    retry_after = 60
    if hasattr(response, "headers"):
        retry_after_value = response.headers.get("Retry-After")
        if retry_after_value is not None:
            try:
                retry_after = int(retry_after_value)
            except (TypeError, ValueError):
                retry_after = 60
    return jsonify({"error": "rate_limit_exceeded", "retry_after": retry_after}), 429


def init_limiter(app: Flask) -> Limiter:
    """Initialize and register the shared Flask-Limiter instance.

    Args:
        app: Flask application instance.

    Returns:
        The configured limiter instance.
    """
    storage_uri = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    app.config.setdefault("RATELIMIT_STORAGE_URI", storage_uri)
    app.config.setdefault("RATELIMIT_DEFAULT", "100 per minute")
    app.config.setdefault("RATELIMIT_DEFAULTS_PER_IP", "1000 per hour")
    app.config.setdefault("RATELIMIT_KEY_FUNC", _get_limiter_key)

    limiter = Limiter(
        key_func=_get_limiter_key,
        default_limits=["100 per minute", "1000 per hour"],
        storage_uri=storage_uri,
        strategy="fixed-window",
        app=app,
        headers_enabled=True,
    )
    limiter.error_message = "rate_limit_exceeded"
    limiter._rate_limit_exceeded = _rate_limit_exceeded
    app.config["RATELIMIT_ENABLED"] = True
    return limiter


limiter = None


def get_limiter() -> Limiter:
    """Return the shared global limiter instance."""
    global limiter
    if limiter is None:
        raise RuntimeError("Limiter has not been initialized with init_limiter(app)")
    return limiter


__all__ = [
    "LOGIN_LIMIT",
    "REGISTER_LIMIT",
    "PASSWORD_RESET_LIMIT",
    "MFA_VERIFY_LIMIT",
    "API_DEFAULT_LIMIT",
    "limiter",
    "init_limiter",
    "get_limiter",
]
