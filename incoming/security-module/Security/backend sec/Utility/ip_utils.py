"""Utilities for safely extracting and handling client IP addresses.

Warning:
    Never trust ``X-Forwarded-For`` unless the application is behind a trusted
    reverse proxy or load balancer. Configure Flask's ``ProxyFix`` middleware so
    that only the proxy chain is trusted and spoofed headers are rejected.

Example:
    >>> from flask import Flask, request
    >>> app = Flask(__name__)
    >>> @app.route('/demo')
    ... def demo():
    ...     return get_client_ip(request)
"""

from __future__ import annotations

import ipaddress
from typing import Any


def _is_valid_ip(value: str) -> bool:
    """Validate that a candidate string is a real IPv4 or IPv6 address.

    Args:
        value: Candidate IP string to validate.

    Returns:
        ``True`` if the value is a valid IP literal, otherwise ``False``.
    """
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def get_client_ip(request: Any) -> str:
    """Extract the client IP address from a Flask request safely.

    The function checks a standard sequence of proxy headers in order of trust
    precedence, validates each candidate using ``ipaddress``, and falls back to
    ``request.remote_addr``. The left-most IP in ``X-Forwarded-For`` is treated as
    the original client, while the right-most IP represents the last proxy that
    forwarded the request.

    Args:
        request: A Flask request object exposing headers and ``remote_addr``.

    Returns:
        A validated client IP string, or ``"unknown"`` if no valid IP is found.
    """
    headers = getattr(request, "headers", {})
    if headers is None:
        headers = {}

    for header_name in ("X-Forwarded-For", "X-Real-IP", "CF-Connecting-IP"):
        header_value = headers.get(header_name)
        if not header_value:
            continue

        if header_name == "X-Forwarded-For":
            candidates = [part.strip() for part in str(header_value).split(",") if part.strip()]
            if candidates:
                candidate = candidates[0]
                if _is_valid_ip(candidate):
                    return candidate
            continue

        candidate = str(header_value).strip()
        if _is_valid_ip(candidate):
            return candidate

    remote_addr = getattr(request, "remote_addr", None)
    if remote_addr:
        remote_addr = str(remote_addr).strip()
        if _is_valid_ip(remote_addr):
            return remote_addr

    return "unknown"


def is_private_ip(ip: str) -> bool:
    """Determine whether an IP address is private or loopback-only.

    Args:
        ip: IP address string to evaluate.

    Returns:
        ``True`` when the address is within a private, loopback, link-local, or
        similar non-public range; otherwise ``False``.
    """
    if not isinstance(ip, str):
        return False

    try:
        parsed_ip = ipaddress.ip_address(ip.strip())
    except ValueError:
        return False

    return (
        parsed_ip.is_private
        or parsed_ip.is_loopback
        or parsed_ip.is_link_local
        or parsed_ip.is_reserved
        or parsed_ip.is_multicast
    )


def anonymize_ip(ip: str) -> str:
    """Mask the last octet of an IPv4 address for privacy-safe log entry creation.

    This preserves the network prefix while anonymizing the host identifier for
    GDPR-oriented logging practices. IPv6 addresses are normalized to a masked
    form by retaining the first 64 bits and replacing the trailing 64 bits with
    ``:0`` placeholders.

    Args:
        ip: IP address string to anonymize.

    Returns:
        A privacy-masked IP string. If the input is invalid, it returns
        ``"unknown"``.
    """
    if not isinstance(ip, str):
        return "unknown"

    cleaned_ip = ip.strip()
    if not cleaned_ip:
        return "unknown"

    try:
        parsed_ip = ipaddress.ip_address(cleaned_ip)
    except ValueError:
        return "unknown"

    if isinstance(parsed_ip, ipaddress.IPv4Address):
        octets = parsed_ip.exploded.split(".")
        octets[-1] = "0"
        return ".".join(octets)

    if isinstance(parsed_ip, ipaddress.IPv6Address):
        hextets = parsed_ip.exploded.split(":")
        if len(hextets) < 8:
            return "::"
        masked = ["0000"] * 4
        return ":".join(masked)

    return "unknown"


__all__ = ["get_client_ip", "is_private_ip", "anonymize_ip"]
