import jwt
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.operations.models import AuditLog
from apps.patients.models import Patient

PASSWORD = "safe-password-123"
FAST_HASHER = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


@FAST_HASHER
class AuthTests(TestCase):
    def setUp(self):
        cache.clear()  # login throttle state lives in the cache
        self.admin = User.objects.create_user(username="admin", password=PASSWORD, role="admin")
        self.doctor = User.objects.create_user(username="doctor", password=PASSWORD, role="doctor")
        self.client = APIClient()

    def obtain(self, username="admin", password=PASSWORD):
        response = APIClient().post("/api/auth/login", {"unique_id": username, "password": password}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def bearer(self, access):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return client

    def test_login_issues_rs256_tokens_verifiable_with_public_key(self):
        tokens = self.obtain("doctor")
        claims = jwt.decode(tokens["access"], settings.JWT_PUBLIC_KEY, algorithms=["RS256"],
                            audience="mediflow", issuer="mediflow-core")
        self.assertEqual(claims["token_type"], "access")
        self.assertEqual(claims["user_id"], str(self.doctor.id))
        self.assertEqual(claims["role"], "doctor")
        self.assertEqual(jwt.get_unverified_header(tokens["access"])["alg"], "RS256")

    def test_bearer_token_authenticates_api_requests(self):
        response = self.bearer(self.obtain("doctor")["access"]).get("/api/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "doctor")

    def test_forged_token_is_rejected(self):
        forged = jwt.encode({"user_id": self.admin.id, "token_type": "access", "role": "admin"}, "guess-" * 8, algorithm="HS256")
        self.assertEqual(self.bearer(forged).get("/api/me").status_code, 401)

    def test_refresh_rotates_and_old_refresh_is_revoked(self):
        tokens = self.obtain()
        rotated = self.client.post("/api/auth/token/refresh", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(rotated.status_code, 200)
        self.assertNotEqual(rotated.data["refresh"], tokens["refresh"])
        reused = self.client.post("/api/auth/token/refresh", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(reused.status_code, 401)

    def test_refresh_picks_up_role_changes(self):
        tokens = self.obtain("doctor")
        self.doctor.role = "nurse"
        self.doctor.save()
        rotated = self.client.post("/api/auth/token/refresh", {"refresh": tokens["refresh"]}, format="json")
        claims = jwt.decode(rotated.data["access"], settings.JWT_PUBLIC_KEY, algorithms=["RS256"], audience="mediflow")
        self.assertEqual(claims["role"], "nurse")

    def test_refresh_denied_for_deactivated_user(self):
        tokens = self.obtain("doctor")
        self.doctor.is_active = False
        self.doctor.save()
        response = self.client.post("/api/auth/token/refresh", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_logout_revokes_refresh_token(self):
        tokens = self.obtain()
        self.assertEqual(self.client.post("/api/auth/logout", {"refresh": tokens["refresh"]}, format="json").status_code, 200)
        response = self.client.post("/api/auth/token/refresh", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_jwks_publishes_public_key_only(self):
        response = self.client.get("/api/auth/jwks")
        self.assertEqual(response.status_code, 200)
        key = response.data["keys"][0]
        self.assertEqual((key["kty"], key["alg"]), ("RSA", "RS256"))
        self.assertNotIn("d", key)

    def test_change_password_requires_current_password_and_revokes_sessions(self):
        tokens = self.obtain("doctor")
        client = self.bearer(tokens["access"])
        wrong = client.post("/api/auth/change-password", {"old_password": "nope", "new_password": "another-password-456",
                                                          "confirm_password": "another-password-456"}, format="json")
        self.assertEqual(wrong.status_code, 400)
        changed = client.post("/api/auth/change-password", {"old_password": PASSWORD, "new_password": "another-password-456",
                                                            "confirm_password": "another-password-456"}, format="json")
        self.assertEqual(changed.status_code, 200)
        self.assertIn("access", changed.data)
        stale = self.client.post("/api/auth/token/refresh", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(stale.status_code, 401)
        self.obtain("doctor", "another-password-456")

    def test_failed_login_is_audited(self):
        response = self.client.post("/api/auth/login", {"unique_id": "admin", "password": "wrong"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertTrue(AuditLog.objects.filter(action="auth.login_failed", entity_id="admin").exists())


@FAST_HASHER
class RbacTests(TestCase):
    def setUp(self):
        cache.clear()  # login throttle state lives in the cache
        self.admin = User.objects.create_user(username="admin", password=PASSWORD, role="admin")
        self.student = User.objects.create_user(username="student", password=PASSWORD, role="student")
        self.it = User.objects.create_user(username="it", password=PASSWORD, role="it")
        Patient.objects.create(full_name="Synthetic Patient", sex="Female", phone="0")

    def as_user(self, username):
        client = APIClient()
        access = client.post("/api/auth/login", {"unique_id": username, "password": PASSWORD}, format="json").data["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return client

    def test_anonymous_cannot_register_staff(self):
        response = APIClient().post("/api/auth/register/staff", {"unique_id": "x", "password": PASSWORD, "role": "admin"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(User.objects.filter(username="x").exists())

    def test_non_admin_cannot_register_staff(self):
        response = self.as_user("student").post("/api/auth/register/staff", {"unique_id": "x", "password": PASSWORD, "role": "admin"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_admin_registers_staff_with_valid_role_only(self):
        client = self.as_user("admin")
        created = client.post("/api/auth/register/staff", {"unique_id": "nurse1", "password": PASSWORD, "role": "nurse"}, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(User.objects.get(username="nurse1").role, "nurse")
        bad = client.post("/api/auth/register/staff", {"unique_id": "s2", "password": PASSWORD, "role": "student"}, format="json")
        self.assertEqual(bad.status_code, 400)

    def test_public_register_cannot_choose_admin_role(self):
        response = APIClient().post("/api/register", {"staffId": "sneaky", "password": PASSWORD, "role": "admin"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.get(username="sneaky").role, "reception")

    def test_student_cannot_read_patient_records_or_queue(self):
        client = self.as_user("student")
        self.assertEqual(client.get("/api/patients").status_code, 403)
        # Queue and dashboard permissions are tested in the Go patient-flow service.

    def test_it_staff_cannot_read_patient_records(self):
        self.assertEqual(self.as_user("it").get("/api/patients").status_code, 403)

    def test_only_admin_role_manages_users_and_departments(self):
        self.assertEqual(self.as_user("it").get("/api/users").status_code, 403)
        self.assertEqual(self.as_user("admin").get("/api/users").status_code, 200)
        self.assertEqual(self.as_user("admin").post("/api/departments", {"name": "Lab", "code": "lab"}, format="json").status_code, 201)
