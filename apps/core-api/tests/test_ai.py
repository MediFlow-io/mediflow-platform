from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.ai import client as ai_client
from apps.operations.models import AuditLog

PASSWORD = "safe-password-123"
SUGGESTION = {"suggested_esi": 2, "risk_level": "HIGH", "reasons": ["High-risk complaint"], "model_version": "test",
              "requires_clinician_review": True}


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AiProxyTests(TestCase):
    def setUp(self):
        for role in ("nurse", "student", "reception"):
            User.objects.create_user(username=role, password=PASSWORD, role=role)

    def as_user(self, username):
        client = APIClient()
        client.force_authenticate(User.objects.get(username=username))
        return client

    @mock.patch.object(ai_client, "call", return_value={"answer": "Cool the burn", "emergency": False})
    def test_any_signed_in_user_can_ask(self, call):
        response = self.as_user("student").post("/api/ai/ask", {"question": "burn?"}, format="json")
        self.assertEqual(response.status_code, 200)
        call.assert_called_once_with("/ai/ask", {"question": "burn?"})

    def test_ask_requires_login(self):
        self.assertEqual(APIClient().post("/api/ai/ask", {"question": "burn?"}, format="json").status_code, 401)

    def test_ask_validates_question(self):
        client = self.as_user("student")
        self.assertEqual(client.post("/api/ai/ask", {"question": ""}, format="json").status_code, 400)
        self.assertEqual(client.post("/api/ai/ask", {"question": "x" * 501}, format="json").status_code, 400)

    @mock.patch.object(ai_client, "call", side_effect=ai_client.AIUnavailable)
    def test_service_failure_returns_503_not_an_invented_answer(self, call):
        response = self.as_user("student").post("/api/ai/ask", {"question": "burn?"}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("answer", response.data)

    @mock.patch.object(ai_client, "call", return_value=SUGGESTION)
    def test_nurse_gets_triage_suggestion_without_identifiers_and_it_is_audited(self, call):
        response = self.as_user("nurse").post("/api/ai/triage", {
            "chief_complaint": "chest pain", "age_years": 40, "vitals": {"heart_rate": 90},
            "patient_name": "Synthetic Person", "patientId": 7}, format="json")
        self.assertEqual(response.status_code, 200)
        sent = call.call_args.args[1]
        self.assertNotIn("patient_name", sent)
        self.assertNotIn("patientId", sent)
        entry = AuditLog.objects.get(action="ai.triage_suggested")
        self.assertEqual(entry.details["suggested_esi"], 2)
        self.assertNotIn("chest pain", str(entry.details))

    def test_non_clinical_roles_cannot_request_triage(self):
        for role in ("student", "reception"):
            self.assertEqual(self.as_user(role).post("/api/ai/triage", {}, format="json").status_code, 403)

    def test_health_endpoint_is_public(self):
        response = APIClient().get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")


class AiClientTests(TestCase):
    @override_settings(AI_SERVICE_URL="http://127.0.0.1:9", AI_SERVICE_TIMEOUT=0.5)
    def test_unreachable_service_raises_unavailable(self):
        with self.assertRaises(ai_client.AIUnavailable):
            ai_client.call("/ai/ask", {"question": "x"})
