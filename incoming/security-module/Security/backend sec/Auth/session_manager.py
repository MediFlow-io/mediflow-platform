"""Redis-backed session tracking and login-attempt lockout management.

Tracking both the user ID and IP address matters because password stuffing and
credential attacks often target a single account from one or many IPs, while
account takeover attempts can also come from many accounts behind the same IP. By
combining both signals, the system can distinguish user-specific abuse from
shared-source attack patterns and respond accordingly.

Example:
    >>> manager = SessionManager(redis_client)
    >>> manager.record_failed_login("u-123", "203.0.113.10")
    1
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Final


class SessionManager:
    """Track failed login attempts, lockout state, and active user sessions in Redis."""

    _MAX_FAILED_ATTEMPTS: Final[int] = 5
    _LOCKOUT_DURATION_MINUTES: Final[int] = 30
    _SESSION_TTL_SECONDS: Final[int] = 60 * 60 * 24  # 24 hours
    _ATTEMPT_TTL_SECONDS: Final[int] = 60 * 60  # 1 hour
    _IP_TTL_SECONDS: Final[int] = 60 * 60  # 1 hour
    _LOCKOUT_TTL_SECONDS: Final[int] = _LOCKOUT_DURATION_MINUTES * 60

    def __init__(self, redis_client: Any) -> None:
        """Initialize the session manager with a Redis client.

        Args:
            redis_client: Redis client instance with standard ``set``, ``incr``,
                ``get``, ``delete``, and ``keys``/``scan`` APIs.
        """
        self.redis_client = redis_client

    def _user_attempt_key(self, user_id: str) -> str:
        """Return the Redis key for a user's failed login attempts."""
        return f"auth:failed_attempts:user:{user_id}"

    def _ip_attempt_key(self, ip: str) -> str:
        """Return the Redis key for failed attempts associated with an IP."""
        return f"auth:failed_attempts:ip:{ip}"

    def _user_lock_key(self, user_id: str) -> str:
        """Return the Redis key that marks a user as locked out."""
        return f"auth:lock:user:{user_id}"

    def _ip_lock_key(self, ip: str) -> str:
        """Return the Redis key that marks an IP as locked or suspicious."""
        return f"auth:lock:ip:{ip}"

    def _session_key(self, jti: str) -> str:
        """Return the Redis key for a session entry."""
        return f"auth:session:{jti}"

    def _user_session_index_key(self, user_id: str) -> str:
        """Return the Redis set key for session IDs for a user."""
        return f"auth:user_sessions:{user_id}"

    def record_failed_login(self, user_id: str, ip: str) -> int:
        """Record a failed login and enforce lockout thresholds.

        The function increments both the per-user and per-IP counters. If either
        counter reaches five failed attempts, the user account is locked for 30
        minutes. All counters use Redis TTLs to avoid permanent retention.

        Args:
            user_id: Unique user identifier.
            ip: Client IP address associated with the failed attempt.

        Returns:
            The current failed-attempt count for the user.
        """
        if not user_id or not ip:
            raise ValueError("user_id and ip must be provided")

        user_key = self._user_attempt_key(str(user_id))
        ip_key = self._ip_attempt_key(str(ip))

        user_count = self.redis_client.incr(user_key)
        ip_count = self.redis_client.incr(ip_key)

        self.redis_client.expire(user_key, self._ATTEMPT_TTL_SECONDS)
        self.redis_client.expire(ip_key, self._IP_TTL_SECONDS)

        if user_count >= self._MAX_FAILED_ATTEMPTS or ip_count >= self._MAX_FAILED_ATTEMPTS:
            self.lock_account(str(user_id), duration_minutes=self._LOCKOUT_DURATION_MINUTES)

        return int(user_count)

    def is_locked_out(self, user_id: str) -> bool:
        """Check whether a user account is currently locked out."""
        if not user_id:
            return False

        key = self._user_lock_key(str(user_id))
        return bool(self.redis_client.exists(key))

    def lock_account(self, user_id: str, duration_minutes: int = 30) -> None:
        """Lock a user account for a given duration."""
        if not user_id:
            raise ValueError("user_id must be provided")

        key = self._user_lock_key(str(user_id))
        ttl = max(int(duration_minutes) * 60, 1)
        self.redis_client.setex(key, ttl, "locked")

    def unlock_account(self, user_id: str) -> None:
        """Unlock a user account by deleting the lock key."""
        if not user_id:
            raise ValueError("user_id must be provided")
        self.redis_client.delete(self._user_lock_key(str(user_id)))

    def clear_failed_attempts(self, user_id: str) -> None:
        """Clear a user's failed login attempts after a successful login."""
        if not user_id:
            raise ValueError("user_id must be provided")
        self.redis_client.delete(self._user_attempt_key(str(user_id)))

    def create_session(self, user_id: str, jti: str, ip: str, user_agent: str) -> None:
        """Create a session entry for a user and bind it to the JWT jti."""
        if not user_id or not jti:
            raise ValueError("user_id and jti must be provided")

        session_payload = {
            "user_id": str(user_id),
            "jti": str(jti),
            "ip": str(ip or "unknown"),
            "user_agent": str(user_agent or "unknown"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        key = self._session_key(str(jti))
        self.redis_client.setex(key, self._SESSION_TTL_SECONDS, json.dumps(session_payload, separators=(",", ":")))

        user_set_key = self._user_session_index_key(str(user_id))
        self.redis_client.sadd(user_set_key, str(jti))
        self.redis_client.expire(user_set_key, self._SESSION_TTL_SECONDS)

    def invalidate_session(self, jti: str) -> None:
        """Invalidate one session by JWT jti."""
        if not jti:
            raise ValueError("jti must be provided")

        session_key = self._session_key(str(jti))
        raw = self.redis_client.get(session_key)
        if raw:
            try:
                payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                user_id = payload.get("user_id")
                if user_id:
                    self.redis_client.srem(self._user_session_index_key(str(user_id)), str(jti))
            except (TypeError, ValueError):
                pass

        self.redis_client.delete(session_key)

    def invalidate_all_sessions(self, user_id: str) -> None:
        """Invalidate every session for a user, e.g., after password change."""
        if not user_id:
            raise ValueError("user_id must be provided")

        user_index_key = self._user_session_index_key(str(user_id))
        session_ids = self.redis_client.smembers(user_index_key) or []

        for token_id in session_ids:
            self.invalidate_session(str(token_id))

        self.redis_client.delete(user_index_key)

    def get_active_sessions(self, user_id: str) -> list[dict]:
        """List active session records for a user."""
        if not user_id:
            return []

        user_index_key = self._user_session_index_key(str(user_id))
        jtis = self.redis_client.smembers(user_index_key) or []
        sessions: list[dict] = []

        for jti in jtis:
            raw = self.redis_client.get(self._session_key(str(jti)))
            if not raw:
                continue
            try:
                payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                sessions.append(payload)
            except (TypeError, ValueError):
                continue

        return sessions


__all__ = ["SessionManager"]
