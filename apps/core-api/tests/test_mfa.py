import time
from unittest import mock

import pyotp
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import TotpDevice, User
from apps.accounts.throttles import RefreshRateThrottle
from apps.operations.models import AuditLog

PASSWORD = "safe-password-123"
FAST_HASHER = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


def code_for(secret, offset=0):
    return pyotp.TOTP(secret).at(int(time.time()) + offset)


@FAST_HASHER
class MfaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.doctor = User.objects.create_user(username="doctor", password=PASSWORD, role="doctor", display_name="Doc")
        self.admin = User.objects.create_user(username="admin", password=PASSWORD, role="admin", display_name="Admin")
        User.objects.create_user(username="stu", password=PASSWORD, role="student", display_name="Stu")

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def login(self, username="doctor"):
        return APIClient().post("/api/auth/login", {"unique_id": username, "password": PASSWORD}, format="json")

    def enable(self, user):
        client = self.as_user(user)
        secret = client.post("/api/auth/mfa/setup").json()["secret"]
        self.assertEqual(client.post("/api/auth/mfa/confirm", {"code": code_for(secret)}, format="json").status_code, 200)
        return secret

    def test_setup_shows_a_qr_code_and_needs_a_valid_first_code(self):
        client = self.as_user(self.doctor)
        setup = client.post("/api/auth/mfa/setup").json()
        self.assertTrue(setup["qrSvg"].startswith("data:image/svg+xml;base64,"))
        self.assertIn("issuer=MediFlow", setup["otpauthUri"])
        self.assertEqual(client.post("/api/auth/mfa/confirm", {"code": "000000"}, format="json").status_code, 400)
        self.assertEqual(client.get("/api/auth/mfa/status").json(), {"enabled": False, "required": False})
        self.assertEqual(client.post("/api/auth/mfa/confirm", {"code": code_for(setup["secret"])}, format="json").status_code, 200)
        self.assertEqual(client.get("/api/auth/mfa/status").json()["enabled"], True)
        self.assertEqual(client.post("/api/auth/mfa/setup").status_code, 409, "turn it off before replacing it")
        self.assertEqual(self.as_user(User.objects.get(username="stu")).post("/api/auth/mfa/setup").status_code, 403)

    def test_login_needs_the_code_once_enabled_and_codes_cannot_be_replayed(self):
        secret = self.enable(self.doctor)
        first = self.login()
        self.assertEqual(first.status_code, 200)
        body = first.json()
        self.assertTrue(body["mfa_required"])
        self.assertNotIn("access", body, "no tokens before the second step")

        client = APIClient()
        self.assertEqual(client.post("/api/auth/mfa/verify", {"mfa_token": body["mfa_token"], "code": "123456"}, format="json").status_code, 401)
        self.assertEqual(client.post("/api/auth/mfa/verify", {"mfa_token": "forged", "code": code_for(secret)}, format="json").status_code, 401)
        # The confirm step used the current code already, so use the next one.
        res = client.post("/api/auth/mfa/verify", {"mfa_token": body["mfa_token"], "code": code_for(secret, 30)}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertIn("access", res.json())
        again = APIClient().post("/api/auth/mfa/verify", {"mfa_token": self.login().json()["mfa_token"], "code": code_for(secret, 30)}, format="json")
        self.assertEqual(again.status_code, 401, "the same code can't be used twice")
        self.assertTrue(AuditLog.objects.filter(action="auth.mfa_failed").exists())

    @override_settings(MFA_REQUIRED_ROLES=frozenset({"doctor"}))
    def test_required_roles_are_told_to_set_up_and_cannot_turn_it_off(self):
        body = self.login().json()
        self.assertTrue(body["mfa_setup_required"])
        self.assertIn("access", body)
        self.assertNotIn("mfa_setup_required", self.login("admin").json())
        secret = self.enable(self.doctor)
        res = self.as_user(self.doctor).post("/api/auth/mfa/disable", {"password": PASSWORD, "code": code_for(secret, 30)}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_disable_needs_password_and_code_and_admin_can_reset(self):
        secret = self.enable(self.doctor)
        client = self.as_user(self.doctor)
        self.assertEqual(client.post("/api/auth/mfa/disable", {"password": "wrong", "code": code_for(secret, 30)}, format="json").status_code, 400)
        self.assertEqual(client.post("/api/auth/mfa/disable", {"password": PASSWORD, "code": code_for(secret, 30)}, format="json").status_code, 200)
        self.assertFalse(TotpDevice.objects.exists())

        self.enable(self.doctor)
        self.assertEqual(self.as_user(self.doctor).post(f"/api/users/{self.doctor.id}/reset-mfa").status_code, 403)
        self.assertEqual(self.as_user(self.admin).post(f"/api/users/{self.doctor.id}/reset-mfa").json(), {"reset": True})
        self.assertIn("access", self.login().json(), "after a reset, the password alone signs in again")
        self.assertTrue(AuditLog.objects.filter(action="auth.mfa_reset").exists())

    def test_refresh_is_rate_limited(self):
        # DRF reads rates at import time, so set this throttle's rate directly.
        with mock.patch.object(RefreshRateThrottle, "rate", "2/min", create=True):
            codes = [APIClient().post("/api/auth/token/refresh", {"refresh": "nonsense"}, format="json").status_code for _ in range(3)]
        self.assertEqual(codes, [401, 401, 429])
