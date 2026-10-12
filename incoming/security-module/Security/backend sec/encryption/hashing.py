"""Secure password and token hashing utilities.

Passwords must be hashed; tokens may be hashed with SHA-256 since they are
already high-entropy.

Why bcrypt and Argon2id are used instead of MD5 or SHA-1:
    - BCrypt and Argon2id are memory-hard password hashing algorithms designed to
      resist offline brute-force and GPU-assisted attacks.
    - MD5 and SHA-1 are fast hashes that are vulnerable to rainbow tables and
      inexpensive brute-force attempts when used for passwords.
    - Passwords should never be stored in reversible or fast formats.

Example:
    >>> password_hash = hash_password("StrongP@ssw0rd!")
    >>> verify_password("StrongP@ssw0rd!", password_hash)
    True
    >>> reset_hash = hash_token("abc123reset-token")
    >>> verify_token_hash("abc123reset-token", reset_hash)
    True
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Final

from passlib.context import CryptContext


_PWD_CONTEXT: Final[CryptContext] = CryptContext(
    schemes=["bcrypt", "argon2"],
    default="bcrypt",
    bcrypt__rounds=12,
    argon2__time_cost=3,
    argon2__memory_cost=65536,
    argon2__parallelism=4,
)


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt by default.

    BCrypt remains the default choice because it is widely supported, has a
    proven password-hashing pedigree, and is configured with a cost factor of 12
    to increase resistance to brute-force attacks. Argon2id is supported as an
    optional upgrade path when the deployment environment prefers the newer
    memory-hard design.

    Args:
        plain: The plaintext password to hash.

    Returns:
        A salted bcrypt hash string suitable for secure storage.

    Raises:
        ValueError: If the input password is empty or not a string.
    """
    if not isinstance(plain, str):
        raise TypeError("plain must be a string")
    if not plain:
        raise ValueError("password cannot be empty")

    return _PWD_CONTEXT.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored password hash.

    Args:
        plain: The plaintext password supplied by the user.
        hashed: The stored password hash.

    Returns:
        ``True`` when the password matches the stored hash, otherwise ``False``.

    Raises:
        TypeError: If either input is not a string.
        ValueError: If the plaintext password is empty.
    """
    if not isinstance(plain, str):
        raise TypeError("plain must be a string")
    if not isinstance(hashed, str):
        raise TypeError("hashed must be a string")
    if not plain:
        raise ValueError("password cannot be empty")

    return _PWD_CONTEXT.verify(plain, hashed)


def needs_rehash(hashed: str) -> bool:
    """Check whether a stored hash should be re-generated with a stronger scheme.

    This function exists to support migration away from older algorithms such as
    weaker bcrypt rounds or legacy unsalted hashes. It is especially useful when
    rotating password hashing configurations and enforcing stronger policy.

    Args:
        hashed: The stored hash string to inspect.

    Returns:
        ``True`` when the hash matches an old/legacy scheme or a weaker
        configuration that should be upgraded; otherwise ``False``.
    """
    if not isinstance(hashed, str):
        raise TypeError("hashed must be a string")
    if not hashed:
        return False

    return _PWD_CONTEXT.needs_update(hashed)


def hash_token(token: str) -> str:
    """Hash a high-entropy token using SHA-256.

    Tokens such as password reset links or email verification values are already
    high-entropy secrets. For them, SHA-256 is appropriate for deterministic
    comparison and storage while avoiding the operational cost of bcrypt or
    Argon2 for non-password secrets.

    Args:
        token: A high-entropy token to hash.

    Returns:
        A hex-encoded SHA-256 digest of the token.

    Raises:
        TypeError: If the token is not a string.
        ValueError: If the token is empty.
    """
    if not isinstance(token, str):
        raise TypeError("token must be a string")
    if not token:
        raise ValueError("token cannot be empty")

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token_hash(token: str, hashed: str) -> bool:
    """Verify a token against its hash using a constant-time comparison.

    Args:
        token: The raw token to verify.
        hashed: The stored SHA-256 hash of the token.

    Returns:
        ``True`` if the token matches the stored hash, otherwise ``False``.

    Raises:
        TypeError: If either value is not a string.
        ValueError: If the token is empty.
    """
    if not isinstance(token, str):
        raise TypeError("token must be a string")
    if not isinstance(hashed, str):
        raise TypeError("hashed must be a string")
    if not token:
        raise ValueError("token cannot be empty")

    expected = hash_token(token)
    return hmac.compare_digest(expected, hashed)


__all__ = [
    "hash_password",
    "verify_password",
    "needs_rehash",
    "hash_token",
    "verify_token_hash",
]
