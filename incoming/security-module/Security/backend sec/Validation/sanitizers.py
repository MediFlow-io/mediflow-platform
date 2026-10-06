"""Sanitization helpers for user-controlled content.

Sanitization is defense-in-depth. Always use parameterized queries and React's
auto-escaping as primary defenses.

These helpers reduce the risk of XSS, path traversal, wildcard abuse, and log
injection by stripping or escaping dangerous content before it is stored or
rendered. They are not a substitute for secure SQL query construction or safe
frontend rendering.
"""

from __future__ import annotations

import os
import re

import bleach


_ALLOWED_TAGS: set[str] = {"p", "br", "strong", "em", "ul", "ol", "li", "a"}
_ALLOWED_ATTRS: dict[str, list[str]] = {"a": ["href", "title", "target"]}


def sanitize_html(dirty: str) -> str:
    """Sanitize HTML for safe rich-text fields.

    This mitigates stored XSS by removing script tags, event handlers, and other
    dangerous markup while preserving a small allowlist of safe formatting tags.

    Args:
        dirty: Raw user-supplied HTML string.

    Returns:
        Clean HTML that is safe for storage or rendering in a constrained context.
    """
    if dirty is None:
        return ""
    if not isinstance(dirty, str):
        raise TypeError("dirty must be a string")

    sanitized = bleach.clean(
        dirty,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        strip=True,
        protocols=["http", "https", "mailto"],
    )
    return sanitized


def strip_all_html(dirty: str) -> str:
    """Strip all HTML tags and return plain text.

    This mitigates reflected and stored HTML injection when a field is meant to be
    plain text rather than rich text, such as notes or names that are later shown
    without formatting.

    Args:
        dirty: Raw user content that may include HTML markup.

    Returns:
        Plain text with tags removed.
    """
    if dirty is None:
        return ""
    if not isinstance(dirty, str):
        raise TypeError("dirty must be a string")

    return bleach.clean(dirty, tags=[], attributes={}, strip=True)


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal and unsafe file access.

    Attackers may attempt to use ``../`` or absolute paths to escape intended file
    storage directories. This function strips path separators and unsafe
    characters before returning a safe basename.

    Args:
        filename: Proposed file name.

    Returns:
        A sanitized filename without traversal or shell-unsafe characters.
    """
    if filename is None:
        return ""
    if not isinstance(filename, str):
        raise TypeError("filename must be a string")

    name = os.path.basename(filename)
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    sanitized = sanitized.strip("._ ")
    return sanitized or "file"


def sanitize_sql_like(value: str) -> str:
    """Escape SQL wildcard characters for a LIKE pattern.

    Attackers can abuse ``%`` and ``_`` to bypass filtering when user input is used
    in SQL LIKE clauses. Escaping these characters prevents wildcard queries from
    matching unintended rows.

    Args:
        value: Raw user value intended for a LIKE query.

    Returns:
        A value with SQL wildcard characters escaped.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("value must be a string")

    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def escape_for_log(value: str) -> str:
    """Escape newline and carriage return characters for safe logging.

    This mitigates log injection where malicious input adds fake log lines or
    impersonates other log entries by inserting control characters.

    Args:
        value: A raw value that will be written to logs.

    Returns:
        A sanitized string safe for logging.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("value must be a string")

    return value.replace("\r", "\\r").replace("\n", "\\n")


__all__ = [
    "sanitize_html",
    "strip_all_html",
    "sanitize_filename",
    "sanitize_sql_like",
    "escape_for_log",
]
