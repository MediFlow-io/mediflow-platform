"""RS256 key material for the JWTs Django issues.

Django is the only service that holds the private key. Every other service
verifies tokens with the public key, fetched from GET /api/auth/jwks.

Keys come from JWT_PRIVATE_KEY / JWT_PUBLIC_KEY (PEM text) or from PEM files in
JWT_KEYS_DIR. In DEBUG only, a missing key pair is generated into JWT_KEYS_DIR so
`docker compose up` and local runs need no manual step. Production must supply keys.
"""
import base64
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.exceptions import ImproperlyConfigured

PRIVATE_FILE = "jwt_private.pem"
PUBLIC_FILE = "jwt_public.pem"


def _write_exclusive(path: Path, data: bytes, mode: int) -> bool:
    """Create the file only if it does not exist; return False if another process won the race."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        return False
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    return True


def _generate_pair(keys_dir: Path) -> None:
    keys_dir.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    # Public key is written first so a reader never sees a private key without its pair.
    if _write_exclusive(keys_dir / PUBLIC_FILE, public_pem, 0o644):
        _write_exclusive(keys_dir / PRIVATE_FILE, private_pem, 0o600)


def load_keys(keys_dir: Path, debug: bool) -> tuple[str, str]:
    private_pem = os.getenv("JWT_PRIVATE_KEY", "").replace("\\n", "\n")
    public_pem = os.getenv("JWT_PUBLIC_KEY", "").replace("\\n", "\n")
    if private_pem and public_pem:
        return private_pem, public_pem

    private_path, public_path = keys_dir / PRIVATE_FILE, keys_dir / PUBLIC_FILE
    if not private_path.exists():
        if not debug:
            raise ImproperlyConfigured(
                "JWT keys missing: set JWT_PRIVATE_KEY/JWT_PUBLIC_KEY or provide PEM files in JWT_KEYS_DIR."
            )
        _generate_pair(keys_dir)
    return private_path.read_text(), public_path.read_text()


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def public_jwk(public_pem: str) -> dict:
    """The verifying key as an RFC 7517 JWK; kid is a stable fingerprint of the key."""
    numbers = serialization.load_pem_public_key(public_pem.encode()).public_numbers()
    kid = hashlib.sha256(public_pem.strip().encode()).hexdigest()[:16]
    return {"kty": "RSA", "use": "sig", "alg": "RS256", "kid": kid,
            "n": _b64url_uint(numbers.n), "e": _b64url_uint(numbers.e)}
