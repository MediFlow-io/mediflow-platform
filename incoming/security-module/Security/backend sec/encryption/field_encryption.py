"""Application-layer encryption for sensitive healthcare data.

Do NOT use for passwords — use hashing.py instead.

Fernet provides authenticated encryption using AES-128-CBC and HMAC, which is
suitable for encrypting sensitive database fields such as phone numbers,
medical notes, and government identifiers. This module is intended for
structured field-level encryption, not password hashing.

Example:
    >>> patient = {"phone_number": "+2348012345678"}
    >>> encrypted = encrypt_dict(patient, ["phone_number"])
    >>> decrypted = decrypt_dict(encrypted, ["phone_number"])
    >>> decrypted["phone_number"] == patient["phone_number"]
    True
"""

from __future__ import annotations

from typing import Any

from cryptography.fernet import Fernet, InvalidToken

try:
    from security.encryption.key_manager import get_fernet_key
except ImportError:  # pragma: no cover - fallback for environments where the module is not yet wired in.
    try:
        from backend.security.encryption.key_manager import get_fernet_key
    except ImportError:  # pragma: no cover - last-resort fallback for local execution.
        def get_fernet_key() -> bytes:
            """Return a Fernet key loaded from the environment.

            This fallback is intentionally defensive: it allows the module to work
            in standalone/local contexts even before the production key manager is
            fully wired into the app.
            """
            import os

            key = os.getenv("FERNET_KEY")
            if not key:
                raise EncryptionError("FERNET_KEY is not configured")
            return key.encode("utf-8")


class EncryptionError(Exception):
    """Raised when field encryption or decryption fails."""


def _get_fernet() -> Fernet:
    """Construct and return a configured Fernet instance.

    Returns:
        A Fernet cipher object initialized with the active application key.

    Raises:
        EncryptionError: If the key cannot be loaded or is invalid.
    """
    try:
        key = get_fernet_key()
    except Exception as exc:  # pragma: no cover - defensive path
        raise EncryptionError("Unable to load encryption key") from exc

    if isinstance(key, str):
        key_bytes = key.encode("utf-8")
    elif isinstance(key, bytes):
        key_bytes = key
    else:
        raise EncryptionError("Encryption key must be a string or bytes value")

    try:
        return Fernet(key_bytes)
    except Exception as exc:  # pragma: no cover - defensive path
        raise EncryptionError("Invalid Fernet key format") from exc


def encrypt_field(plaintext: str) -> str:
    """Encrypt a sensitive value using Fernet.

    Args:
        plaintext: The cleartext value to encrypt.

    Returns:
        A base64-encoded encrypted value as a string.

    Raises:
        EncryptionError: If encryption fails or the input is invalid.
    """
    if plaintext is None:
        return None
    if not isinstance(plaintext, str):
        raise EncryptionError("plaintext must be a string or None")

    try:
        cipher = _get_fernet()
        return cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        raise EncryptionError("Failed to encrypt field") from exc


def decrypt_field(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted value.

    Args:
        ciphertext: The encrypted value returned by ``encrypt_field``.

    Returns:
        The original cleartext string.

    Raises:
        EncryptionError: If the ciphertext is invalid, corrupted, or cannot be
        decrypted.
    """
    if ciphertext is None:
        return None
    if not isinstance(ciphertext, str):
        raise EncryptionError("ciphertext must be a string or None")

    try:
        cipher = _get_fernet()
        return cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError("Failed to decrypt field: invalid or tampered ciphertext") from exc
    except Exception as exc:
        raise EncryptionError("Failed to decrypt field") from exc


def encrypt_dict(data: dict, fields: list[str]) -> dict:
    """Encrypt specific sensitive fields in a dictionary.

    Args:
        data: A dictionary containing the original values.
        fields: Names of fields to encrypt.

    Returns:
        A dictionary copy with the requested fields encrypted.

    Raises:
        EncryptionError: If a field value cannot be encrypted.
    """
    if data is None:
        return None
    if not isinstance(data, dict):
        raise EncryptionError("data must be a dictionary or None")
    if fields is None:
        return data.copy()

    encrypted = data.copy()
    for field_name in fields:
        if field_name not in encrypted:
            continue
        value = encrypted[field_name]
        encrypted[field_name] = encrypt_field(value)
    return encrypted


def decrypt_dict(data: dict, fields: list[str]) -> dict:
    """Decrypt specific fields in a dictionary.

    Args:
        data: A dictionary containing encrypted values.
        fields: Names of fields to decrypt.

    Returns:
        A dictionary copy with the requested fields decrypted.

    Raises:
        EncryptionError: If a field value cannot be decrypted.
    """
    if data is None:
        return None
    if not isinstance(data, dict):
        raise EncryptionError("data must be a dictionary or None")
    if fields is None:
        return data.copy()

    decrypted = data.copy()
    for field_name in fields:
        if field_name not in decrypted:
            continue
        value = decrypted[field_name]
        decrypted[field_name] = decrypt_field(value)
    return decrypted


__all__ = [
    "EncryptionError",
    "encrypt_field",
    "decrypt_field",
    "encrypt_dict",
    "decrypt_dict",
]
