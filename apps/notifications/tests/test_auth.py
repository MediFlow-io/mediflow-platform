import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import AuthError, Verifier

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeKeys:
    """Stands in for PyJWKClient: a JWKS with two keys, 'old' and 'current'."""
    keys = {"old": OTHER.public_key(), "current": KEY.public_key()}

    def get_signing_key(self, kid):
        if kid not in self.keys:
            raise jwt.PyJWKClientError(f'Unable to find a signing key that matches: "{kid}"')
        return type("Key", (), {"key": self.keys[kid]})()

    def get_signing_keys(self):
        return [type("Key", (), {"key": k})() for k in self.keys.values()]


def verifier():
    v = Verifier("http://unused/jwks", "mediflow-core", "mediflow")
    v._keys = FakeKeys()
    return v


def token(key=KEY, headers=None, **overrides):
    claims = {"user_id": "7", "role": "student", "token_type": "access", "iss": "mediflow-core", "aud": "mediflow",
              "exp": int(time.time()) + 300, **overrides}
    return "Bearer " + jwt.encode(claims, key, algorithm="RS256", headers=headers)


def test_valid_access_token_without_kid_tries_every_key():
    assert verifier().verify(token()) == 7  # Django's tokens carry no kid


def test_valid_access_token_with_kid():
    assert verifier().verify(token(headers={"kid": "current"})) == 7


@pytest.mark.parametrize("header", [
    None, "", "Token abc", "Bearer not-a-jwt",
    token(key=rsa.generate_private_key(public_exponent=65537, key_size=2048)),
    token(headers={"kid": "old"}), token(headers={"kid": "unknown"}),
    token(token_type="refresh"), token(exp=int(time.time()) - 5),
    token(iss="someone-else"), token(aud="other"), token(user_id="seven"),
    "Bearer " + jwt.encode({"user_id": "7", "token_type": "access", "exp": int(time.time()) + 60},
                           "not-the-rsa-key-but-long-enough-0123456789", algorithm="HS256"),
])
def test_rejected(header):
    with pytest.raises(AuthError):
        verifier().verify(header)
