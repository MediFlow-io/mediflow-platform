"""JWT creation, validation, and revocation for the healthcare application.

RS256 is preferred over HS256 because it enables asymmetric signing, which is
more secure for multi-service and distributed applications. With RS256, the
private key signs tokens while separate services can verify them with the public
key without ever sharing the signing secret. This reduces blast radius and keeps
JWT signing material isolated to a trusted issuer.

Example:
    >>> token = create_access_token("user-123", ["student"], expires_minutes=15)
    >>> payload = decode_token(token)
    >>> payload["sub"]
    'user-123'
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Final

import jwt

from security.encryption.key_manager import get_jwt_private_key, get_jwt_public_key


JWT_ISSUER: Final[str] = "futa-health"
JWT_AUDIENCE: Final[str] = "futa-health-app"


class InvalidToken(Exception):
    """Raised when a JWT fails signature, issuer, audience, or structure validation."""


class TokenExpired(Exception):
    """Raised when a JWT has passed its expiration time."""


class TokenRevoked(Exception):
    """Raised when a JWT has been revoked via the blocklist."""


class JWTHandler:
    """Create, validate, revoke, and inspect JWTs using RS256 signing."""

    def __init__(self, redis_client: Any | None = None) -> None:
        """Initialize the JWT handler with an injected Redis client.

        Args:
            redis_client: Redis client used for revocation blocklist management.
        """
        self.redis_client = redis_client

    def create_access_token(
        self,
        user_id: str,
        roles: list[str] | tuple[str, ...],
        expires_minutes: int = 15,
    ) -> str:
        """Create a short-lived access token for a user.

        Args:
            user_id: Unique subject identifier for the user.
            roles: List of role names assigned to the user.
            expires_minutes: TTL for the token in minutes.

        Returns:
            A signed JWT access token.
        """
        if not user_id:
            raise ValueError("user_id cannot be empty")

        now = dt.datetime.now(dt.timezone.utc)
        payload = {
            "sub": str(user_id),
            "roles": list(roles),
            "iat": int(now.timestamp()),
            "exp": int((now + dt.timedelta(minutes=expires_minutes)).timestamp()),
            "jti": str(uuid.uuid4()),
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
        }
        private_key = get_jwt_private_key()
        return jwt.encode(payload, private_key, algorithm="RS256")

    def create_refresh_token(self, user_id: str, expires_days: int = 7) -> str:
        """Create a long-lived refresh token for session renewal.

        Args:
            user_id: Unique subject identifier for the user.
            expires_days: TTL for the refresh token in days.

        Returns:
            A signed JWT refresh token.
        """
        if not user_id:
            raise ValueError("user_id cannot be empty")

        now = dt.datetime.now(dt.timezone.utc)
        payload = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int((now + dt.timedelta(days=expires_days)).timestamp()),
            "jti": str(uuid.uuid4()),
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "type": "refresh",
        }
        private_key = get_jwt_private_key()
        return jwt.encode(payload, private_key, algorithm="RS256")

    def decode_token(self, token: str) -> dict[str, Any]:
        """Validate and decode a JWT, verifying integrity and required claims.

        The function confirms the token signature, expiration time, issuer, and
        audience before returning the decoded payload. It also rejects revoked
        tokens before the payload is handed back to callers.

        Args:
            token: JWT string to decode.

        Returns:
            Decoded JWT payload as a dictionary.

        Raises:
            InvalidToken: If the token is malformed or fails verification.
            TokenExpired: If the token is expired.
            TokenRevoked: If the token is present in the Redis blocklist.
        """
        if not token or not isinstance(token, str):
            raise InvalidToken("Token is missing or invalid.")

        try:
            public_key = get_jwt_public_key()
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
                options={"require": ["exp", "iss", "aud", "sub", "jti"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpired("JWT has expired.") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidToken("JWT is invalid or verification failed.") from exc

        if self.is_token_revoked(token):
            raise TokenRevoked("JWT has been revoked.")

        return payload

    def revoke_token(self, token: str) -> None:
        """Add a JWT jti to Redis with a TTL matching the remaining lifetime.

        Args:
            token: JWT string to revoke.

        Raises:
            InvalidToken: If the token cannot be decoded for its jti or expiration.
        """
        if self.redis_client is None:
            raise RuntimeError("Redis client is required for token revocation")

        payload = self.decode_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")

        if not jti:
            raise InvalidToken("JWT is missing a jti claim and cannot be revoked.")
        if exp is None:
            raise InvalidToken("JWT is missing an exp claim and cannot be revoked.")

        now_ts = int(dt.datetime.now(dt.timezone.utc).timestamp())
        remaining_ttl = max(int(exp) - now_ts, 1)
        self.redis_client.setex(f"jwt:blocklist:{jti}", remaining_ttl, "revoked")

    def is_token_revoked(self, token: str) -> bool:
        """Check whether a JWT has been revoked by examining the Redis blocklist.

        Args:
            token: JWT string to inspect.

        Returns:
            ``True`` if the token has been revoked, otherwise ``False``.
        """
        if self.redis_client is None:
            return False

        try:
            payload = jwt.decode(
                token,
                get_jwt_public_key(),
                algorithms=["RS256"],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
                options={"require": ["exp", "iss", "aud", "sub", "jti"]},
                leeway=0,
            )
        except jwt.PyJWTError:
            return False

        jti = payload.get("jti")
        if not jti:
            return False
        return bool(self.redis_client.exists(f"jwt:blocklist:{jti}"))


def create_access_token(user_id: str, roles: list[str] | tuple[str, ...], expires_minutes: int = 15) -> str:
    """Create a signed access token using the default JWT handler."""
    return JWTHandler().create_access_token(user_id, roles, expires_minutes)


def create_refresh_token(user_id: str, expires_days: int = 7) -> str:
    """Create a signed refresh token using the default JWT handler."""
    return JWTHandler().create_refresh_token(user_id, expires_days)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT using the default JWT handler."""
    return JWTHandler().decode_token(token)


def revoke_token(token: str) -> None:
    """Revoke a JWT using the default JWT handler."""
    raise NotImplementedError("Use JWTHandler(redis_client=...) and call revoke_token on the instance.")


def is_token_revoked(token: str) -> bool:
    """Check whether a JWT is revoked using the default JWT handler."""
    return JWTHandler().is_token_revoked(token)


__all__ = [
    "JWTHandler",
    "InvalidToken",
    "TokenExpired",
    "TokenRevoked",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "revoke_token",
    "is_token_revoked",
]
