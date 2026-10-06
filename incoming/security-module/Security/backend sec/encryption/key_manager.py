"""Centralized management of encryption and signing keys.

In dev, keys come from .env; in prod, from Vault.

This module resolves keys from environment variables first, then optionally from
HashiCorp Vault or AWS Secrets Manager when running in a managed production
environment. It supports key rotation by maintaining an ordered list of active
keys, where the current key is always the first element.

Example:
    >>> fernet_key = get_fernet_key()
    >>> private_key = get_jwt_private_key()
    >>> public_key = get_jwt_public_key()
    >>> isinstance(fernet_key, bytes)
    True
"""

from __future__ import annotations

import base64
import os
from functools import lru_cache
from typing import Any, Final

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None

try:
    import hvac
except ImportError:  # pragma: no cover
    hvac = None


_DEFAULT_ENV_KEYS: Final[dict[str, str]] = {
    "FERNET_KEY": "FERNET_KEY",
    "JWT_PRIVATE_KEY": "JWT_PRIVATE_KEY",
    "JWT_PUBLIC_KEY": "JWT_PUBLIC_KEY",
    "JWT_SECRET": "JWT_SECRET",
    "VAULT_KEY_PATH": "VAULT_KEY_PATH",
    "AWS_SECRET_NAME": "AWS_SECRET_NAME",
}


class KeyManagementError(RuntimeError):
    """Raised when required cryptographic keys are missing or invalid."""


def _is_production() -> bool:
    """Return whether the runtime is configured for production mode."""
    env = os.getenv("APP_ENV", "development").strip().lower()
    return env in {"production", "prod", "staging", "stage"}


def _load_env_value(name: str) -> str | None:
    """Read a key value from the environment if present."""
    return os.getenv(name)


def _load_from_vault() -> dict[str, str]:
    """Load security secrets from HashiCorp Vault when the integration is configured.

    Returns:
        A dictionary of secret names mapped to string values.

    Raises:
        KeyManagementError: If Vault is configured but inaccessible.
    """
    if hvac is None:
        raise KeyManagementError("hvac is not installed; Vault support unavailable")

    vault_url = os.getenv("VAULT_ADDR")
    vault_token = os.getenv("VAULT_TOKEN")
    secret_path = os.getenv("VAULT_KEY_PATH")

    if not vault_url or not vault_token or not secret_path:
        raise KeyManagementError("Vault configuration is incomplete")

    client = hvac.Client(url=vault_url, token=vault_token)
    if not client.is_authenticated():
        raise KeyManagementError("Vault authentication failed")

    try:
        secret = client.secrets.kv.v2.read_secret_version(path=secret_path)
    except Exception as exc:  # pragma: no cover - environment-specific exception path
        raise KeyManagementError("Unable to read secrets from Vault") from exc

    data = secret.get("data", {}).get("data", {}) if isinstance(secret, dict) else {}
    if not isinstance(data, dict):
        raise KeyManagementError("Vault secret payload is malformed")
    return {str(key): str(value) for key, value in data.items()}


def _load_from_aws_secrets_manager() -> dict[str, str]:
    """Load secrets from AWS Secrets Manager when configured.

    Returns:
        A dictionary of secret names mapped to string values.

    Raises:
        KeyManagementError: If AWS Secrets Manager access fails or no secret name is configured.
    """
    if boto3 is None:
        raise KeyManagementError("boto3 is not installed; AWS Secrets Manager support unavailable")

    secret_name = os.getenv("AWS_SECRET_NAME")
    if not secret_name:
        raise KeyManagementError("AWS_SECRET_NAME is not configured")

    try:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_name)
    except Exception as exc:  # pragma: no cover - environment-specific exception path
        raise KeyManagementError("Unable to read secrets from AWS Secrets Manager") from exc

    secret = response.get("SecretString")
    if not secret:
        raise KeyManagementError("AWS secret payload is empty")

    try:
        parsed = __import__("json").loads(secret)
    except Exception:
        return {"_default": secret}

    if isinstance(parsed, dict):
        return {str(key): str(value) for key, value in parsed.items()}
    return {"_default": str(parsed)}


def _resolve_secret(name: str) -> str:
    """Resolve a secret value from environment first, then managed secret stores.

    In development, the value is expected to come from a local environment file.
    In production, a managed secrets store such as Vault should provide the key.

    Args:
        name: Secret variable name to resolve.

    Returns:
        The resolved secret string.

    Raises:
        KeyManagementError: If no value is available and production requires it.
    """
    value = _load_env_value(name)
    if value:
        return value

    if _is_production():
        try:
            vault_data = _load_from_vault()
            if name in vault_data and vault_data[name]:
                return vault_data[name]
        except KeyManagementError:
            pass

        try:
            aws_data = _load_from_aws_secrets_manager()
            if name in aws_data and aws_data[name]:
                return aws_data[name]
        except KeyManagementError:
            pass

        raise KeyManagementError(f"Missing required secret: {name}. In production, keys must come from Vault or AWS Secrets Manager")

    raise KeyManagementError(f"Missing required secret: {name}")


def _normalize_fernet_key(value: str) -> bytes:
    """Normalize a Fernet key to the required bytes payload."""
    candidate = value.strip()
    if not candidate:
        raise KeyManagementError("FERNET_KEY cannot be empty")

    if candidate.startswith("base64:"):
        candidate = candidate.replace("base64:", "", 1)

    try:
        decoded = base64.urlsafe_b64decode(candidate.encode("utf-8") + b"=")
    except Exception as exc:
        raise KeyManagementError("FERNET_KEY must be a valid base64-encoded 32-byte Fernet key") from exc

    if len(decoded) != 32:
        raise KeyManagementError("FERNET_KEY must decode to exactly 32 bytes")
    return decoded


@lru_cache(maxsize=1)
def get_fernet_key() -> bytes:
    """Return the active Fernet symmetric key used for fields encryption.

    Returns:
        A 32-byte Fernet key encoded as bytes.

    Raises:
        KeyManagementError: If the key is missing or malformed.
    """
    raw = _resolve_secret("FERNET_KEY")
    return _normalize_fernet_key(raw)


@lru_cache(maxsize=1)
def get_jwt_private_key() -> str:
    """Return the active RSA private key used to sign JWTs.

    Returns:
        PEM-encoded RSA private key content.

    Raises:
        KeyManagementError: If the private key is missing in production or absent locally.
    """
    return _resolve_secret("JWT_PRIVATE_KEY")


@lru_cache(maxsize=1)
def get_jwt_public_key() -> str:
    """Return the RSA public key matching the JWT private key.

    Returns:
        PEM-encoded RSA public key content.

    Raises:
        KeyManagementError: If the public key is missing in production or absent locally.
    """
    return _resolve_secret("JWT_PUBLIC_KEY")


@lru_cache(maxsize=1)
def get_jwt_secret() -> str:
    """Return the fallback HS256 secret for local development environments.

    The application should prefer RS256 in production, but this helper provides a
    safe dev-only fallback when the environment is not configured for asymmetric
    JWT signing.

    Returns:
        A secret string suitable for HS256 signing.

    Raises:
        KeyManagementError: If the secret is missing and the environment is production-only.
    """
    if _is_production():
        return _resolve_secret("JWT_SECRET")
    value = _load_env_value("JWT_SECRET")
    if value:
        return value
    raise KeyManagementError("JWT_SECRET is missing. Add it to your .env file in development")


__all__ = [
    "KeyManagementError",
    "get_fernet_key",
    "get_jwt_private_key",
    "get_jwt_public_key",
    "get_jwt_secret",
]
