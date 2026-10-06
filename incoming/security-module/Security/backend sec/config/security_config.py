"""Flask security configuration helpers.

This module centralizes hardening settings for secure sessions, CORS, and proxy
handling in a Flask application.

Example:
    >>> from flask import Flask
    >>> app = Flask(__name__)
    >>> configure_security(app)
    >>> configure_cors(app)
    >>> configure_proxy_fix(app)
"""

from __future__ import annotations

import os
from datetime import timedelta

from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix


def configure_security(app: Flask) -> None:
    """Apply secure cookie and request hardening settings to a Flask app."""
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("APP_ENV", "development").lower() in {"production", "prod"}
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=15)
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["WTF_CSRF_TIME_LIMIT"] = 3600


def configure_cors(app: Flask) -> None:
    """Configure a strict CORS policy for trusted frontend origins."""
    allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
    allowed_origins = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]

    CORS(
        app,
        resources={r"/*": {"origins": allowed_origins or ["http://localhost:3000", "http://127.0.0.1:3000"]}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-CSRF-TOKEN"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        max_age=3600,
    )


def configure_proxy_fix(app: Flask) -> None:
    """Enable Werkzeug ProxyFix only for deployments behind a trusted reverse proxy.

    Only enable if behind a trusted reverse proxy.
    """
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_port=1,
        x_prefix=1,
    )


__all__ = ["configure_security", "configure_cors", "configure_proxy_fix"]
