"""Access-token checks: RS256, verified against the core API's JWKS, same rules as the Go services."""
import jwt
from jwt import PyJWKClient

INVALID = "Given token not valid for any token type"


class AuthError(Exception):
    pass


class Verifier:
    def __init__(self, jwks_url: str, issuer: str, audience: str):
        # Caches the keys for 5 minutes; a token naming an unknown key triggers a fresh fetch (rotation).
        self._keys = PyJWKClient(jwks_url, cache_keys=True, lifespan=300, timeout=10)
        self._issuer, self._audience = issuer, audience

    def _candidates(self, token: str) -> list:
        """The key matching the token's kid, or every signing key when it has none (Django's tokens don't)."""
        kid = jwt.get_unverified_header(token).get("kid")
        if kid:
            return [self._keys.get_signing_key(kid).key]
        return [k.key for k in self._keys.get_signing_keys()]

    def verify(self, header: str | None) -> int:
        """Returns the user id from an `Authorization: Bearer ...` header."""
        if not header or not header.startswith("Bearer "):
            raise AuthError("Authentication credentials were not provided.")
        token = header.removeprefix("Bearer ").strip()
        try:
            keys = self._candidates(token)
        except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
            raise AuthError(INVALID) from exc
        claims = None
        for key in keys:
            try:
                claims = jwt.decode(token, key, algorithms=["RS256"], issuer=self._issuer or None,
                                    audience=self._audience or None, options={"require": ["exp", "user_id"]})
                break
            except jwt.InvalidSignatureError:
                continue
            except jwt.PyJWTError as exc:
                raise AuthError(INVALID) from exc
        if claims is None or claims.get("token_type") != "access":
            raise AuthError(INVALID)
        try:
            return int(claims["user_id"])
        except (TypeError, ValueError) as exc:
            raise AuthError(INVALID) from exc
