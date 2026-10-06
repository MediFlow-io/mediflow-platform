"""Security headers middleware for all Flask responses.

This module attaches a hardened set of HTTP response headers to minimize the
impact of common web vulnerabilities such as MIME confusion, clickjacking,
referrer leakage, and XSS. It also avoids HSTS on localhost development builds.
"""

from __future__ import annotations

import os

from flask import Response


def add_security_headers(response: Response) -> Response:
    """Attach a hardened set of security headers to a Flask response.

    X-Content-Type-Options: prevents browsers from MIME-sniffing and executing unexpected content types.
    X-Frame-Options: denies embedding the site in a frame to mitigate clickjacking.
    Referrer-Policy: limits referrer leakage to the origin when navigating cross-site.
    Permissions-Policy: disables access to sensitive device APIs unless explicitly allowed.
    Strict-Transport-Security: forces HTTPS for all subdomains in production to protect transport security.
    Content-Security-Policy: restricts resource loading to trusted sources and blocks frame embedding.
    Cross-Origin-Opener-Policy: isolates browsing context to reduce cross-window attack surface.
    Cross-Origin-Resource-Policy: restricts cross-origin resource sharing to same-origin requests.
    """
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

    if os.getenv("APP_ENV", "development").strip().lower() in {"production", "prod"}:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


__all__ = ["add_security_headers"]
