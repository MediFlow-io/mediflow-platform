from django.test import SimpleTestCase

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from config.jwt_keys import normalize_pem


class NormalizePemTests(SimpleTestCase):
    """Keys pasted into a hosting dashboard often lose their line breaks."""

    def test_every_paste_form_becomes_a_valid_key(self):
        pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        for variant in (pem, pem.replace("\n", " "), pem.replace("\n", "\n"), pem.replace("\n", "\r\n"), f"  {pem}  "):
            serialization.load_pem_private_key(normalize_pem(variant).encode(), None)

    def test_other_text_is_left_alone(self):
        self.assertEqual(normalize_pem("  not a key "), "not a key")
        self.assertEqual(normalize_pem(""), "")
