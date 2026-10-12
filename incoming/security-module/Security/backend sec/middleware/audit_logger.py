"""Structured audit logging for security and compliance events.

Never log PII. If you must log, use anonymize_ip() and mask.

This logger emits JSON to stdout in a format suitable for log aggregation while
redacting sensitive fields such as passwords, tokens, secrets, SSNs, and card
numbers. The output is intentionally structured for later analysis in SIEM or
ELK-style log pipelines.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

import structlog

from security.utils.ip_utils import anonymize_ip


_SENSITIVE_KEYS: Final[set[str]] = {
    "password",
    "token",
    "secret",
    "ssn",
    "card_number",
    "authorization",
    "api_key",
    "mfa_code",
    "session_id",
}


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _serialize_value(value: Any) -> Any:
    """Convert values to serializable JSON-safe forms."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple, set)):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    return str(value)


def _redact_sensitive_data(data: Any) -> Any:
    """Redact sensitive keys from structured data before logging.

    Args:
        data: Arbitrary payload to redact.

    Returns:
        A JSON-safe object with sensitive fields replaced by "[REDACTED]".
    """
    if isinstance(data, dict):
        redacted: dict[str, Any] = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if any(sensitive in key_lower for sensitive in _SENSITIVE_KEYS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_sensitive_data(value)
        return redacted

    if isinstance(data, list):
        return [_redact_sensitive_data(item) for item in data]

    return data


class AuditLogger:
    """Structured audit logger for authentication, access, and security events."""

    def __init__(self, file_path: str | None = None) -> None:
        """Create an audit logger that emits JSON to stdout and optionally to a file.

        Args:
            file_path: Optional file path for local log persistence. When provided,
                a file handler is attached in addition to stdout.
        """
        self.file_path = file_path
        self._configure_structlog()

    def _configure_structlog(self) -> None:
        """Configure structlog JSON logging for stdout and optional file streaming."""
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.PrintLoggerFactory(file=open(os.devnull, "w")),
            cache_logger_on_first_use=True,
        )

        if self.file_path:
            path = Path(self.file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

    def _log_event(self, event_type: str, **kwargs: Any) -> None:
        """Emit a JSON log event after redaction and metadata normalization."""
        payload = {
            "timestamp": _utc_now_iso(),
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
        }
        for key, value in kwargs.items():
            if key == "ip" and value:
                payload[key] = anonymize_ip(str(value))
            elif key in {"details", "detail"}:
                payload["details"] = _redact_sensitive_data(_serialize_value(value))
            else:
                payload[key] = _serialize_value(value)

        safe_payload = _redact_sensitive_data(payload)
        structlog.get_logger("audit").info(event_type, **safe_payload)

        if self.file_path:
            with open(self.file_path, "a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(safe_payload, ensure_ascii=True) + "\n")

    def log_auth_event(
        self,
        event_type: str,
        user_id: str | None,
        ip: str | None,
        user_agent: str | None,
        success: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log an authentication or session-related security event."""
        self._log_event(
            event_type,
            user_id=user_id,
            ip=ip,
            user_agent=user_agent,
            success=success,
            details=details or {},
        )

    def log_data_access(
        self,
        user_id: str | None,
        resource_type: str,
        resource_id: str | None,
        action: str,
        ip: str | None,
    ) -> None:
        """Log a healthcare data access event for audit and compliance review."""
        self._log_event(
            "data_access",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            ip=ip,
        )

    def log_admin_action(
        self,
        user_id: str | None,
        action: str,
        target: str | None,
        ip: str | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log administrator actions affecting user or system state."""
        self._log_event(
            "admin_action",
            user_id=user_id,
            action=action,
            target=target,
            ip=ip,
            details=details or {},
        )

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log a security event such as IDOR, rate-limit hit, or abuse detection."""
        self._log_event(
            event_type,
            severity=severity,
            details=details or {},
        )


logger = AuditLogger(file_path=os.getenv("AUDIT_LOG_PATH"))


__all__ = ["AuditLogger", "logger"]
